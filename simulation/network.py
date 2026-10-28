"""
network.py -- wireless network model (ESP-NOW stand-in).

Contents
--------
GilbertElliottChannel   two-state burst-loss channel + random latency
                        (logic unchanged from the notebook)
dead_reckon             leader-state extrapolation during blackouts
                        (notebook logic + optional exponential decay, Eq. 26)
LinkStats               per-link counters and recent-loss window
Network                 one directed channel per (sender, receiver) pair,
                        in-flight delivery queue, statistics, link health

FaultEvent / FaultProfile
                        scheduled, seeded communication faults (blackout,
                        independent loss, burst loss, extra latency + jitter)
                        applied INSIDE Network.transmit (no parallel network)

The Network is the single place where packets are lost or delayed.  Every
decision is reported back as a `CommEvent` and stored on the MessageBus, so
the UI shows exactly what the model did.
"""
from __future__ import annotations

import heapq
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .agent import LinkStatus
from .config import Config
from .kinematics import wrap_angle
from .messages import (CommEvent, Message, MessageBus, STATUS_DELAYED,
                       STATUS_LOST, STATUS_OK)


# ---------------------------------------------------------------------------
# Channel model (unchanged maths)
# ---------------------------------------------------------------------------
class GilbertElliottChannel:
    """Two-state (good/bad) burst-loss channel with random latency.

    `transmit(packet)` returns None when the packet is lost, otherwise
    (packet, delay_in_steps).  RNG usage order is identical to the notebook.
    """

    def __init__(self, p_gb=0.025, p_bg=0.22, seed=1,
                 base_delay_steps=1, max_delay_steps=4):
        self.rng = np.random.default_rng(seed)
        self.bad = False
        self.p_gb = min(max(p_gb, 0.0), 1.0)
        self.p_bg = p_bg
        self.base_delay_steps = base_delay_steps
        self.max_delay_steps = max_delay_steps
        self.force_loss = False       # test hook: behave as 100 % loss

    def transmit(self, packet):
        if self.bad:
            if self.rng.random() < self.p_bg:
                self.bad = False
        elif self.rng.random() < self.p_gb:
            self.bad = True
        if self.bad or self.force_loss:
            return None
        delay = int(self.rng.integers(self.base_delay_steps,
                                      self.max_delay_steps + 1))
        out = packet.copy() if hasattr(packet, "copy") else packet
        return out, delay


def dead_reckon(last_packet, age, use_pidr=True, lam=0.0):
    """Extrapolate the leader's last known state forward by `age` seconds.

    use_pidr=False  -> zero-order hold (ZOH): just return the stale packet.
    use_pidr=True   -> propagate through the unicycle kinematics.
    lam > 0         -> velocities decay as exp(-lam * t) (report Eq. 26) so a
                       long blackout converges to a stationary hold instead of
                       integrating a stale velocity forever.  Implemented with
                       the closed-form 'effective age' (1 - e^{-lam a}) / lam,
                       which is exact because v and omega decay together.
    lam = 0         -> original notebook behaviour.
    """
    p = np.array(last_packet, dtype=float).copy()
    if not use_pidr:
        return p
    if lam > 0.0:
        age = (1.0 - np.exp(-lam * age)) / lam
    x, y, th, v, w = p
    if abs(w) < 1e-7:
        x += v * np.cos(th) * age
        y += v * np.sin(th) * age
    else:
        x += (v / w) * (np.sin(th + w * age) - np.sin(th))
        y += (v / w) * (-np.cos(th + w * age) + np.cos(th))
        th += w * age
    p[:3] = [x, y, wrap_angle(th)]
    return p



# ---------------------------------------------------------------------------
# Scheduled communication faults
# ---------------------------------------------------------------------------
FAULT_KINDS = ("blackout", "random_loss", "burst_loss", "latency")


def _check_prob(name: str, v: float) -> float:
    v = float(v)
    if not (math.isfinite(v) and 0.0 <= v <= 1.0):
        raise ValueError(f"{name} must be a probability in [0, 1], got {v!r}")
    return v


def _check_nonneg(name: str, v: float, allow_inf: bool = False) -> float:
    v = float(v)
    if math.isnan(v) or v < 0.0 or (math.isinf(v) and not allow_inf):
        raise ValueError(f"{name} must be a non-negative finite number, got {v!r}")
    return v


@dataclass(frozen=True)
class FaultEvent:
    """One fault active during [start, start + duration) of simulation time.

    kind          meaning / parameters used
    ------------  ----------------------------------------------------------
    blackout      every packet on every link is lost (same mechanism as the
                  existing `set_forced_loss`, so the RNG stream is identical)
    random_loss   independent loss, each packet dropped with `probability`
    burst_loss    correlated loss: per-link two-state chain
                  (`p_good_to_bad`, `p_bad_to_good`); in the bad state a packet
                  is dropped with `loss_in_bad`
    latency       delivered packets get `extra_latency_s` + U(-jitter, jitter)
                  seconds of additional delay (never negative in total)
    """
    kind: str
    start: float
    duration: float
    probability: float = 0.0
    p_good_to_bad: float = 0.0
    p_bad_to_good: float = 1.0
    loss_in_bad: float = 1.0
    extra_latency_s: float = 0.0
    jitter_s: float = 0.0
    label: str = ""

    def __post_init__(self):
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"fault kind must be one of {FAULT_KINDS}, got {self.kind!r}")
        _check_nonneg("start", self.start)
        _check_nonneg("duration", self.duration, allow_inf=True)
        _check_prob("probability", self.probability)
        _check_prob("p_good_to_bad", self.p_good_to_bad)
        _check_prob("p_bad_to_good", self.p_bad_to_good)
        _check_prob("loss_in_bad", self.loss_in_bad)
        _check_nonneg("extra_latency_s", self.extra_latency_s)
        _check_nonneg("jitter_s", self.jitter_s)
        if self.kind == "burst_loss" and self.p_bad_to_good <= 0.0 and self.p_good_to_bad > 0.0:
            raise ValueError("burst_loss with p_bad_to_good = 0 never recovers; "
                             "use blackout or a positive p_bad_to_good")
        if self.kind == "latency" and self.extra_latency_s == 0.0 and self.jitter_s == 0.0:
            raise ValueError("latency fault needs extra_latency_s or jitter_s > 0")

    @property
    def end(self) -> float:
        return self.start + self.duration

    def active(self, now: float) -> bool:
        return self.start - 1e-9 <= now < self.end - 1e-9

    def as_dict(self) -> dict:
        d = {"kind": self.kind, "label": self.label or self.kind,
             "start": self.start,
             "end": None if math.isinf(self.end) else self.end}
        if self.kind == "random_loss":
            d["probability"] = self.probability
        elif self.kind == "burst_loss":
            d.update(p_good_to_bad=self.p_good_to_bad, p_bad_to_good=self.p_bad_to_good,
                     loss_in_bad=self.loss_in_bad)
        elif self.kind == "latency":
            d.update(extra_latency_s=self.extra_latency_s, jitter_s=self.jitter_s)
        return d


@dataclass(frozen=True)
class FaultProfile:
    """A named, immutable schedule of fault events."""
    name: str
    events: Tuple[FaultEvent, ...] = ()
    description: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description,
                "events": [e.as_dict() for e in self.events]}


PROFILE_NAMES = ("none", "blackout", "random_loss", "burst_loss", "latency_jitter",
                 "blackout_latency")


def make_fault_profile(name: str, start: float = 5.0, duration: float = 3.0,
                       probability: float = 0.30, p_good_to_bad: float = 0.15,
                       p_bad_to_good: float = 0.15, loss_in_bad: float = 1.0,
                       extra_latency_s: float = 0.30, jitter_s: float = 0.15) -> FaultProfile:
    """Build one of the standard profiles (all parameters validated).

    none              no fault (default behaviour of the simulator)
    blackout          100 % loss for `duration` s starting at `start`
    random_loss       independent loss with `probability` in the window
    burst_loss        correlated (bursty) loss in the window
    latency_jitter    extra latency + jitter in the window
    blackout_latency  latency/jitter window followed immediately by a blackout
                      (messages that do arrive just before the outage are old)
    """
    if name not in PROFILE_NAMES:
        raise ValueError(f"unknown fault profile {name!r}; choose from {PROFILE_NAMES}")
    if name == "none":
        return FaultProfile("none", (), "no injected faults")
    if name == "blackout":
        ev = (FaultEvent("blackout", start, duration, label="blackout"),)
        return FaultProfile(name, ev, "complete communication blackout")
    if name == "random_loss":
        ev = (FaultEvent("random_loss", start, duration, probability=probability,
                         label="random_loss"),)
        return FaultProfile(name, ev, f"independent packet loss p={probability:g}")
    if name == "burst_loss":
        ev = (FaultEvent("burst_loss", start, duration, p_good_to_bad=p_good_to_bad,
                         p_bad_to_good=p_bad_to_good, loss_in_bad=loss_in_bad,
                         label="burst_loss"),)
        return FaultProfile(name, ev, "correlated burst loss (two-state chain per link)")
    if name == "latency_jitter":
        ev = (FaultEvent("latency", start, duration, extra_latency_s=extra_latency_s,
                         jitter_s=jitter_s, label="latency_jitter"),)
        return FaultProfile(name, ev, "extra latency with jitter")
    ev = (FaultEvent("latency", start, duration, extra_latency_s=extra_latency_s,
                     jitter_s=jitter_s, label="latency_jitter"),
          FaultEvent("blackout", start + duration, duration, label="blackout"))
    return FaultProfile(name, ev, "latency/jitter window followed by a blackout")

# ---------------------------------------------------------------------------
# Per-link statistics
# ---------------------------------------------------------------------------
@dataclass
class LinkStats:
    window: int = 40
    sent: int = 0
    received: int = 0
    lost: int = 0
    latency_sum: float = 0.0
    latency_max: float = 0.0
    last_rx_time: float = 0.0
    recent_lost: Deque[bool] = field(default_factory=deque)

    def __post_init__(self):
        self.recent_lost = deque(maxlen=self.window)

    @property
    def loss_rate(self) -> float:
        return self.lost / self.sent if self.sent else 0.0

    @property
    def avg_latency(self) -> float:
        return self.latency_sum / self.received if self.received else 0.0

    @property
    def recent_loss_rate(self) -> float:
        return (sum(self.recent_lost) / len(self.recent_lost)
                if self.recent_lost else 0.0)


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
class Network:
    """All radio links of the swarm.

    Links are created lazily.  Leader -> follower channels are seeded exactly
    like the notebook (seed + 100 + follower_id); the reverse channels
    (follower -> leader: ACK, HEARTBEAT) use seed + 200 + follower_id.
    """

    def __init__(self, cfg: Config, bus: MessageBus, seed: int = 42,
                 loss_scale: float = 1.0):
        self.cfg = cfg
        self.bus = bus
        self.seed = seed
        self.loss_scale = loss_scale
        self._channels: Dict[Tuple[int, int], GilbertElliottChannel] = {}
        self._stats: Dict[Tuple[int, int], LinkStats] = {}
        self._queue: list = []          # heap of (deliver_time, counter, msg)
        self._counter = 0
        self.forced_loss_all = False
        self._forced_links: set = set()
        # --- scheduled faults (default: none -> behaviour unchanged) -------
        self.profile: FaultProfile = FaultProfile("none")
        self._blackout_active = False
        self._fault_rngs: Dict[Tuple[int, int], np.random.Generator] = {}
        self._burst_bad: Dict[Tuple[Tuple[int, int], int], bool] = {}
        self._event_state: Dict[int, bool] = {}
        self.fault_log: List[dict] = []
        self.fault_counts = {"dropped_by_fault": 0, "delayed_by_fault": 0,
                             "extra_latency_sum": 0.0}

    # ------------------------------------------------------------------
    # Fault schedule
    # ------------------------------------------------------------------
    def set_fault_profile(self, profile: "FaultProfile | str | None") -> None:
        """Install a fault profile (resets fault state; keeps channel RNGs)."""
        if profile is None:
            profile = FaultProfile("none")
        elif isinstance(profile, str):
            profile = make_fault_profile(profile)
        if not isinstance(profile, FaultProfile):
            raise TypeError("profile must be a FaultProfile, a profile name or None")
        self.profile = profile
        self._blackout_active = False
        self._burst_bad.clear()
        self._event_state = {i: False for i in range(len(profile.events))}
        self.fault_log = []
        self.fault_counts = {"dropped_by_fault": 0, "delayed_by_fault": 0,
                             "extra_latency_sum": 0.0}

    def update_faults(self, now: float) -> None:
        """Activate / expire events at simulation time `now` and log edges."""
        for i, ev in enumerate(self.profile.events):
            act = ev.active(now)
            if act != self._event_state.get(i, False):
                self._event_state[i] = act
                self.fault_log.append({"t": round(float(now), 6), "event": ev.label or ev.kind,
                                       "kind": ev.kind, "action": "start" if act else "end",
                                       "profile": self.profile.name})
        self._blackout_active = any(
            ev.kind == "blackout" and self._event_state.get(i, False)
            for i, ev in enumerate(self.profile.events))

    def active_faults(self) -> List[dict]:
        return [ev.as_dict() for i, ev in enumerate(self.profile.events)
                if self._event_state.get(i, False)]

    def _fault_rng(self, link: Tuple[int, int]) -> np.random.Generator:
        if link not in self._fault_rngs:
            s, r = link
            self._fault_rngs[link] = np.random.default_rng(
                [self.seed, 7919, s, r])           # independent of channel RNGs
        return self._fault_rngs[link]

    def _fault_drop(self, link: Tuple[int, int]) -> bool:
        """True if an active random/burst loss event drops this packet."""
        rng = self._fault_rng(link)
        dropped = False
        for i, ev in enumerate(self.profile.events):
            if not self._event_state.get(i, False):
                continue
            if ev.kind == "random_loss":
                if rng.random() < ev.probability:
                    dropped = True
            elif ev.kind == "burst_loss":
                key = (link, i)
                bad = self._burst_bad.get(key, False)
                if bad:
                    if rng.random() < ev.p_bad_to_good:
                        bad = False
                elif rng.random() < ev.p_good_to_bad:
                    bad = True
                self._burst_bad[key] = bad
                if bad and (ev.loss_in_bad >= 1.0 or rng.random() < ev.loss_in_bad):
                    dropped = True
        return dropped

    def _fault_extra_latency(self, link: Tuple[int, int]) -> float:
        extra = 0.0
        rng = self._fault_rng(link)
        for i, ev in enumerate(self.profile.events):
            if ev.kind == "latency" and self._event_state.get(i, False):
                extra += ev.extra_latency_s
                if ev.jitter_s > 0.0:
                    extra += float(rng.uniform(-ev.jitter_s, ev.jitter_s))
        return extra

    def fault_snapshot(self) -> dict:
        return {"profile": self.profile.name, "description": self.profile.description,
                "events": [dict(e.as_dict(), active=bool(self._event_state.get(i, False)))
                           for i, e in enumerate(self.profile.events)],
                "active": self.active_faults(), "blackout_active": self._blackout_active,
                "forced_loss": self.forced_loss_all,
                "log": list(self.fault_log[-20:]), "counts": dict(self.fault_counts)}

    # ------------------------------------------------------------------
    def _channel(self, link: Tuple[int, int]) -> GilbertElliottChannel:
        if link not in self._channels:
            s, r = link
            follower = r if s == 0 else s
            offset = 100 if s == 0 else 200
            ch = GilbertElliottChannel(
                self.cfg.packet_good_to_bad * self.loss_scale,
                self.cfg.packet_bad_to_good,
                self.seed + offset + follower,
                self.cfg.base_delay_steps, self.cfg.max_delay_steps)
            ch.force_loss = self.forced_loss_all
            self._channels[link] = ch
        return self._channels[link]

    def _link_stats(self, link: Tuple[int, int]) -> LinkStats:
        if link not in self._stats:
            self._stats[link] = LinkStats(window=self.cfg.link_window)
        return self._stats[link]

    # ------------------------------------------------------------------
    def transmit(self, msg: Message, now: float, dt: float | None = None) -> CommEvent:
        """Send `msg` through its link; returns (and logs) what happened."""
        dt = self.cfg.dt if dt is None else dt
        link = (msg.sender, msg.receiver)
        stats = self._link_stats(link)
        stats.sent += 1

        ch = self._channel(link)
        ch.force_loss = (self.forced_loss_all or self._blackout_active
                         or link in self._forced_links)
        result = ch.transmit(msg)
        if result is not None and self._fault_drop(link):    # injected loss
            self.fault_counts["dropped_by_fault"] += 1
            result = None
        if result is None:                                   # ---- LOST
            stats.lost += 1
            stats.recent_lost.append(True)
            ev = CommEvent(now, msg.sender, msg.receiver, msg.msg_type,
                           STATUS_LOST, 0.0, msg.sequence)
            self.bus.record(ev)
            return ev

        _, delay_steps = result                              # ---- DELIVERED
        latency = delay_steps * dt
        extra = self._fault_extra_latency(link)
        if extra != 0.0:                                     # injected latency
            latency = max(0.0, latency + extra)
            self.fault_counts["delayed_by_fault"] += 1
            self.fault_counts["extra_latency_sum"] += extra
        stats.received += 1
        stats.recent_lost.append(False)
        stats.latency_sum += latency
        stats.latency_max = max(stats.latency_max, latency)
        stats.last_rx_time = now + (latency if self.cfg.causal_delivery else 0.0)

        if self.cfg.causal_delivery:
            deliver_at = now + latency      # packet really arrives later
        else:
            # Legacy notebook semantics: the packet is usable immediately but
            # its data is considered `latency` seconds old.
            deliver_at = now
            msg.timestamp = now - latency

        self._counter += 1
        heapq.heappush(self._queue, (deliver_at, self._counter, msg))
        status = (STATUS_DELAYED if latency >= self.cfg.delayed_threshold_s
                  else STATUS_OK)
        ev = CommEvent(now, msg.sender, msg.receiver, msg.msg_type,
                       status, latency, msg.sequence)
        self.bus.record(ev)
        return ev

    def poll(self, now: float) -> List[Message]:
        """Return all in-flight messages whose delivery time has arrived."""
        out = []
        while self._queue and self._queue[0][0] <= now + 1e-9:
            out.append(heapq.heappop(self._queue)[2])
        return out

    # ------------------------------------------------------------------
    # Test / experiment hooks
    # ------------------------------------------------------------------
    def set_forced_loss(self, enabled: bool, link: Tuple[int, int] | None = None):
        """Force 100 % packet loss on one link, or on every link."""
        if link is None:
            self.forced_loss_all = enabled
            for ch in self._channels.values():
                ch.force_loss = enabled
        else:
            (self._forced_links.add if enabled else self._forced_links.discard)(link)
            self._channel(link).force_loss = enabled

    # ------------------------------------------------------------------
    # Health + statistics (values come from the real model)
    # ------------------------------------------------------------------
    def link_status(self, receiver: int, now: float) -> LinkStatus:
        st = self._stats.get((0, receiver))
        if st is None or st.sent == 0:
            return LinkStatus.ONLINE
        silent = now - st.last_rx_time
        if silent > self.cfg.offline_timeout_s:
            return LinkStatus.OFFLINE
        if (st.recent_loss_rate > self.cfg.degraded_loss_rate
                or silent > self.cfg.degraded_age_s):
            return LinkStatus.DEGRADED
        return LinkStatus.ONLINE

    def link_is_up(self, sender: int, receiver: int, now: float, timeout: float) -> bool:
        """True if a packet arrived on sender->receiver within `timeout` seconds.

        A link that has not carried any packet yet counts as up until `timeout`
        has elapsed since t = 0 (start-up grace), so a fresh run is connected.
        """
        st = self._stats.get((sender, receiver))
        last = 0.0 if st is None or st.received == 0 else st.last_rx_time
        return (now - last) <= timeout

    def up_links(self, n: int, now: float, down_timeout: float,
                 up_timeout: float) -> List[Tuple[int, int]]:
        """Directed links currently up (the graph is a star around agent 0).

        Downlink (0 -> f) uses `down_timeout`, uplink (f -> 0) `up_timeout`
        because the two carry traffic at very different rates.
        """
        out = []
        for f in range(1, n):
            if self.link_is_up(0, f, now, down_timeout):
                out.append((0, f))
            if self.link_is_up(f, 0, now, up_timeout):
                out.append((f, 0))
        return out

    def snapshot(self) -> dict:
        """Aggregate and per-link statistics for the UI panel."""
        sent = sum(s.sent for s in self._stats.values())
        recv = sum(s.received for s in self._stats.values())
        lost = sum(s.lost for s in self._stats.values())
        lat_sum = sum(s.latency_sum for s in self._stats.values())
        lat_max = max([s.latency_max for s in self._stats.values()] or [0.0])
        links = {}
        for (s, r), st in self._stats.items():
            if s == 0:
                links[r] = {"sent": st.sent, "received": st.received,
                            "lost": st.lost,
                            "loss_rate": round(100 * st.loss_rate, 2),
                            "avg_latency": round(st.avg_latency, 4)}
        return {
            "sent": sent, "received": recv, "lost": lost,
            "loss_rate": round(100.0 * lost / sent, 2) if sent else 0.0,
            "avg_latency": round(lat_sum / recv, 4) if recv else 0.0,
            "max_latency": round(lat_max, 4),
            "links": links,
            "forced_loss": self.forced_loss_all,
            "faults": self.fault_snapshot(),
        }
