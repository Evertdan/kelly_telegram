# bot/handlers/commands.py
# -*- coding: utf-8 -*-

"""
Manejadores para los comandos de Telegram (ej. /start, /help).
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode # Para usar formato en mensajes

# Importar settings para acceder, por ejemplo, a usuarios de debug
try:
    from bot.core.config import settings
    CONFIG_LOADED = True
except ImportError:
     print("[ERROR commands.py] No se pudo importar 'settings'. Funciones de debug podrían fallar.")
     # Dummy settings para que el archivo cargue
     class DummySettings: authorized_debug_user_ids: set = set()
     settings = DummySettings() # type: ignore
     CONFIG_LOADED = False


logger = logging.getLogger(__name__)

# --- Handlers de Comandos ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start."""
    user = update.effective_user
    # Usar el nombre de pila si está disponible
    user_name = user.first_name if user and user.first_name else "usuario"
    logger.info(f"Comando /start recibido de UserID: {user.id if user else 'Desconocido'}")

    # Mensaje de bienvenida personalizado
    welcome_message = (
        f"¡Hola {user_name}! 👋 Soy Kely, tu asistente virtual de Computo Contable Soft.\n\n"
        "Estoy aquí para ayudarte con tus consultas sobre **MiAdminXML** y **MiExpedienteContable**.\n\n"
        "Puedes hacerme preguntas directamente sobre:\n"
        "• Cómo usar los programas\n"
        "• Resolución de problemas comunes\n"
        "• Información de licencias y precios\n"
        "• Requisitos de sistema\n\n"
        "Simplemente escribe tu pregunta. Si necesitas ayuda general sobre cómo interactuar conmigo, usa el comando /help."
    )

    if update.message:
        await update.message.reply_html(welcome_message) # Usar HTML para negritas
        # Alternativa sin formato: await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /help."""
    user = update.effective_user
    logger.info(f"Comando /help recibido de UserID: {user.id if user else 'Desconocido'}")

    help_text = (
        "**¿Cómo usar a Kely?**\n\n"
        "1.  **Haz tu pregunta:** Simplemente escribe tu consulta sobre MiAdminXML o MiExpedienteContable en el chat.\n"
        "2.  **Intentaré responder:** Buscaré en mi base de conocimiento la información más relevante para darte una respuesta precisa.\n"
        "3.  **Sé específico:** Mientras más clara sea tu pregunta, mejor podré ayudarte.\n\n"
        "**Comandos disponibles:**\n"
        "/start - Inicia la conversación y muestra el mensaje de bienvenida.\n"
        "/help - Muestra este mensaje de ayuda.\n"
    )
    # Añadir comando debug si el usuario está autorizado
    if user and CONFIG_LOADED and user.id in settings.authorized_debug_user_ids:
         help_text += "/debug `on`|`off` - Activa/desactiva la vista de fuentes (solo usuarios autorizados).\n"

    if update.message:
         # Usar MarkdownV2 requiere escapar caracteres especiales como ., -, +, !
         # HTML suele ser más fácil de usar para formato simple
         await update.message.reply_html(help_text.replace("**", "<b>").replace("`", "<code>")) # Convertir a HTML simple
         # Alternativa MarkdownV2 (requiere escapar):
         # await update.message.reply_markdown_v2(escaped_help_text)


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Activa o desactiva el modo debug para usuarios autorizados."""
    user = update.effective_user
    if not user: return # No debería pasar con comandos

    logger.info(f"Comando /debug recibido de UserID: {user.id}")

    # Verificar si el usuario está autorizado
    if not CONFIG_LOADED or user.id not in settings.authorized_debug_user_ids:
        logger.warning(f"Usuario {user.id} intentó usar /debug sin autorización.")
        if update.message: await update.message.reply_text("Lo siento, este comando es solo para usuarios autorizados.")
        return

    # Verificar argumento (on/off)
    command_parts = update.message.text.split()
    if len(command_parts) != 2 or command_parts[1].lower() not in ["on", "off"]:
        await update.message.reply_text("Uso: /debug `on` o /debug `off`", parse_mode=ParseMode.MARKDOWN_V2)
        return

    # Guardar estado en user_data (requiere persistencia configurada en main.py)
    if context.user_data is None:
         logger.warning(f"context.user_data no está disponible para UserID {user.id}. ¿Persistencia configurada?")
         await update.message.reply_text("No se pudo cambiar el modo debug (problema de persistencia).")
         return

    mode = command_parts[1].lower()
    if mode == "on":
        context.user_data['debug_mode'] = True
        logger.info(f"Modo debug ACTIVADO para UserID: {user.id}")
        await update.message.reply_text("✅ Modo Debug activado. Ahora verás las fuentes en las respuestas.")
    else: # mode == "off"
        context.user_data['debug_mode'] = False
        logger.info(f"Modo debug DESACTIVADO para UserID: {user.id}")
        await update.message.reply_text("☑️ Modo Debug desactivado.")


# --- Aquí puedes añadir más funciones para otros comandos ---
# async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None: ...