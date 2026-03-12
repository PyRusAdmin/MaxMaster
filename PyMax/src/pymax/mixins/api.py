from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from PyMax.src.pymax.protocols import ClientProtocol
from PyMax.src.pymax.static.enum import Opcode
from PyMax.src.pymax.payloads import SyncPayload, UserAgentPayload

if TYPE_CHECKING:
    from PyMax.src.pymax.types import Chat


class ApiMixin(ClientProtocol):
    """
    Mixin для основных API-запросов к серверу.
    """

    async def _sync(self, user_agent: UserAgentPayload | None = None) -> None:
        """
        Выполняет синхронизацию с сервером.

        :param user_agent: Пользовательский агент.
        :type user_agent: UserAgentPayload | None
        """
        from PyMax.src.pymax.types import Chat, Dialog, Channel, Me, User
        from PyMax.src.pymax.static.enum import ChatType
        from PyMax.src.pymax.utils import MixinsUtils

        logger.info("Starting initial sync")

        if user_agent is None:
            user_agent = self.headers or UserAgentPayload()

        payload = SyncPayload(
            interactive=True,
            token=self._token,
            chats_sync=0,
            contacts_sync=0,
            presence_sync=0,
            drafts_sync=0,
            chats_count=40,
            user_agent=user_agent,
        ).model_dump(by_alias=True)
        try:
            data = await self._send_and_wait(opcode=Opcode.LOGIN, payload=payload)
            raw_payload = data.get("payload", {})

            if error := raw_payload.get("error"):
                MixinsUtils.handle_error(data)

            for raw_chat in raw_payload.get("chats", []):
                try:
                    if raw_chat.get("type") == ChatType.DIALOG.value:
                        self.dialogs.append(Dialog.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHAT.value:
                        self.chats.append(Chat.from_dict(raw_chat))
                    elif raw_chat.get("type") == ChatType.CHANNEL.value:
                        self.channels.append(Channel.from_dict(raw_chat))
                except Exception:
                    logger.exception("Error parsing chat entry")

            for raw_user in raw_payload.get("contacts", []):
                try:
                    user = User.from_dict(raw_user)
                    if user:
                        self.contacts.append(user)
                except Exception:
                    logger.exception("Error parsing contact entry")

            if raw_payload.get("profile", {}).get("contact"):
                self.me = Me.from_dict(raw_payload.get("profile", {}).get("contact", {}))

            logger.info(
                "Sync completed: dialogs=%d chats=%d channels=%d",
                len(self.dialogs),
                len(self.chats),
                len(self.channels),
            )

        except Exception as e:
            logger.exception("Sync failed")
            self.is_connected = False
            if self._ws:
                await self._ws.close()
            self._ws = None
            raise
