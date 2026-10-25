from __future__ import annotations
from dataclasses import dataclass

from . import config
from .gateway import Gateway
from .integrations import Slack
from .knowledge import Knowledge
from .modes import Modes
from .notify import Notifier
from .orchestrator import Orchestrator
from .scheduler import Scheduler
from .skills import SkillRegistry
from .store import Store
from .tasks import Tasks
from .chat import Chat
from .tools import Tools


@dataclass
class Services:
    settings: config.Settings
    store: Store
    gateway: Gateway
    skills: SkillRegistry
    orch: Orchestrator
    scheduler: Scheduler
    kb: Knowledge = None
    modes: Modes = None
    notifier: Notifier = None
    slack: Slack = None
    tasks: Tasks = None
    chat: Chat = None


def build(settings=None, provider=None, tools_transport=None, notify_transport=None, slack_transport=None) -> Services:
    s = settings or config.load()
    store = Store(s.db_path)
    gw = Gateway(s, store, provider)
    skills = SkillRegistry(s.skills_dir)
    kb = Knowledge(store, s)
    orch = Orchestrator(s, store, gw, Tools(s, tools_transport, kb), skills, kb)
    modes = Modes(s, store, gw, orch)
    notifier = Notifier(s, notify_transport)
    svc = Services(s, store, gw, skills, orch, Scheduler(store, orch, modes.run, notifier, kb), kb, modes, notifier)
    svc.slack = Slack(svc, slack_transport)
    svc.tasks, svc.chat = Tasks(modes, store), Chat(store, gw, modes)
    return svc
