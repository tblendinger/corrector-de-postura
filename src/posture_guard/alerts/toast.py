"""Windows Toast Notifications for PostureGuard."""

import logging
from posture_guard.data.models import PostureIssue
from posture_guard.utils import constants

logger = logging.getLogger(__name__)

try:
    from winotify import Notification, audio
except ImportError:
    Notification = None
    audio = None
    logger.warning("winotify not installed. Toast notifications will be disabled.")

class ToastNotifier:
    """Manages Windows toast notifications."""

    def show_posture_alert(self, issues: list[PostureIssue]):
        """Shows a toast notification for posture issues."""
        if Notification is None:
            return
            
        try:
            issues_text = ", ".join([issue.display_name for issue in issues])
            
            toast = Notification(
                app_id=constants.APP_NAME,
                title="¡Corregí tu postura!",
                msg=issues_text,
                duration="short"
            )
            toast.show()
        except Exception as e:
            logger.error("Failed to show posture alert toast: %s", e)

    def show_micropause_reminder(self, interval_min: int = 30):
        """Shows a micropause (1-2 min) break notification."""
        self.show_info(
            title=f"💡 Micropausa recomendada ({interval_min} min)",
            message=(
                f"Llevás {interval_min} minutos sentado. "
                "Tomá una micropausa de 1 a 2 minutos para ponerte de pie, "
                "estirar las piernas y activar el retorno venoso."
            ),
        )

    def show_active_break_reminder(self, interval_min: int = 50):
        """Shows an active break (5-10 min) notification."""
        self.show_info(
            title=f"🚶 Descanso activo necesario ({interval_min}-60 min)",
            message=(
                f"Llevás {interval_min} minutos sentado. "
                "Realizá un descanso activo de 5 a 10 minutos. "
                "Es el límite de tiempo que la columna tolera bajo la misma carga antes de sufrir rigidez."
            ),
        )

    def show_info(self, title: str, message: str):
        """Shows a generic info toast notification."""
        if Notification is None:
            return

        try:
            toast = Notification(
                app_id=constants.APP_NAME,
                title=title,
                msg=message,
                duration="long",
            )
            toast.show()
        except Exception as e:
            logger.error("Failed to show info toast: %s", e)
