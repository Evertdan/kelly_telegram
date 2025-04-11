# bot/core/config.py
# -*- coding: utf-8 -*-

"""
Configuración centralizada para el Bot de Telegram KellyBot.
CORREGIDO: Importar Path desde pathlib, validador debug users.
"""

import logging
import sys
import os
from pathlib import Path # <-- ASEGURAR que Path viene de pathlib
from typing import Optional, Any, Set, List, Literal, get_args

# Usar pydantic-settings y tipos de pydantic
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import (
    Field,
    HttpUrl,
    SecretStr,
    PositiveInt,
    FilePath,
    # Path NO se importa de pydantic
    field_validator,
    model_validator,
    ValidationError
)
from pydantic_core.core_schema import ValidationInfo

# --- Definir Ruta Base del Proyecto ---
try:
    PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
except NameError:
    PROJECT_ROOT = Path.cwd()
    print(f"[ADVERTENCIA Config Bot] No se pudo determinar PROJECT_ROOT, usando CWD: {PROJECT_ROOT}")

# --- Tipos Específicos ---
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# --- Logger ---
logger = logging.getLogger(__name__)
if not logger.hasHandlers():
     handler = logging.StreamHandler(sys.stderr)
     formatter = logging.Formatter('%(asctime)s - %(name)s [%(levelname)s] - %(message)s')
     handler.setFormatter(formatter)
     logger.addHandler(handler)
     logger.setLevel(logging.WARNING)

# --- Helper para resolver rutas ---
def _resolve_path(value: Optional[str]) -> Optional[Path]:
     if value:
         path = Path(value) # Usa pathlib.Path
         if not path.is_absolute():
             if PROJECT_ROOT and PROJECT_ROOT.is_dir():
                 return (PROJECT_ROOT / path).resolve()
             else:
                 logger.warning(f"PROJECT_ROOT no válido, no se puede resolver: {value}")
                 return path
         return path
     return None

# --- Clase Principal de Settings ---
class Settings(BaseSettings):
    """Carga y valida las configuraciones para el Bot de Telegram."""

    # --- Telegram Bot ---
    TELEGRAM_BOT_TOKEN: SecretStr = Field(..., alias='TELEGRAM_BOT_TOKEN') # Obligatorio

    # --- Kelly API Backend ---
    KELLYBOT_API_URL: HttpUrl = Field(default="http://localhost:8000", alias='KELLYBOT_API_URL')
    API_ACCESS_KEY: SecretStr = Field(..., alias='API_ACCESS_KEY') # Obligatorio
    API_TIMEOUT_CONNECT: float = Field(default=10.0, alias='API_TIMEOUT_CONNECT')
    API_TIMEOUT_READ: float = Field(default=180.0, alias='API_TIMEOUT_READ')

    # --- Configuración General del Bot ---
    LOG_LEVEL: LogLevel = Field(default='INFO', alias='LOG_LEVEL')
    TRIGGER_WORD: Optional[str] = Field(default="kelly", alias='TRIGGER_WORD')

    # --- Configuración de Debug ---
    AUTHORIZED_DEBUG_USERS_STR: Optional[str] = Field(default=None, alias='AUTHORIZED_DEBUG_USERS')
    authorized_debug_user_ids: Set[int] = set() # Calculado

    # --- Configuración de Persistencia (Opcional) ---
    PERSISTENCE_FILE_PATH: Optional[Path] = Field( # Usa Path de pathlib
        default=PROJECT_ROOT / "persistence" / "bot_data.pickle",
        alias='PERSISTENCE_FILE_PATH'
    )

    # --- Configuración del Modelo Pydantic Settings ---
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / '.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=False,
    )

    # --- Validadores ---
    @field_validator('LOG_LEVEL', mode='before')
    @classmethod
    def validate_log_level(cls, value: Any) -> str:
        """Valida y normaliza el nivel de log."""
        if not isinstance(value, str): raise ValueError("LOG_LEVEL debe ser str.")
        valid = get_args(LogLevel)
        upper_v = value.upper()
        if upper_v not in valid: raise ValueError(f"LOG_LEVEL inválido: '{value}'. Usar: {valid}")
        return upper_v

    # Validador para procesar usuarios de debug
    @model_validator(mode='after')
    def parse_debug_users_post(self) -> 'Settings':
        """Convierte AUTHORIZED_DEBUG_USERS_STR en un set de IDs enteros."""
        ids_set = set()
        raw_value = getattr(self, 'AUTHORIZED_DEBUG_USERS_STR', None) # Acceso seguro
        if raw_value:
            try:
                ids_str_list = raw_value.split(',')
                for user_id_str in ids_str_list:
                    user_id_str = user_id_str.strip()
                    if user_id_str.isdigit(): ids_set.add(int(user_id_str))
                    elif user_id_str: logger.warning(f"[Config Bot] ID inválido en AUTH...: '{user_id_str}'")
            except Exception as e: logger.error(f"[Config Bot] Error parseando AUTH...: {e}")
        self.authorized_debug_user_ids = ids_set
        logger.debug(f"Usuarios debug cargados: {self.authorized_debug_user_ids}")
        return self

    # Validador/Resolvedor para ruta de persistencia
    @field_validator('PERSISTENCE_FILE_PATH', mode='before')
    @classmethod
    def resolve_persistence_path(cls, value: Any) -> Optional[Path]:
        """Resuelve la ruta del archivo de persistencia relativa a PROJECT_ROOT."""
        return _resolve_path(value) # Usa el helper

# --- Instancia Global de Configuración ---
try:
    settings = Settings()
except ValidationError as e:
    # Usar logger ya definido
    logger.critical("!!! Error CRÍTICO de Validación de Configuración (Bot) !!!")
    logger.critical(f"Revisa tu archivo .env ({PROJECT_ROOT / '.env'}):")
    logger.critical(e)
    # Quitar sys.exit para que pytest pueda reportar el error más limpiamente
    # sys.exit("Error fatal de configuración del bot.")
    raise e # Relanzar la excepción para que pytest la capture
except Exception as e:
    # Usar logger ya definido
    logger.critical(f"!!! Error CRÍTICO Inesperado al Cargar Configuración (Bot) !!!: {e}", exc_info=True)
    # sys.exit("Error fatal inesperado cargando configuración del bot.")
    raise e # Relanzar

# --- Bloque de prueba opcional ---
if __name__ == "__main__":
    print("--- Configuración Cargada para Kelly Telegram Bot ---")
    if 'settings' in locals():
         # Usar model_dump para excluir SecretStr por defecto
         print(settings.model_dump_json(indent=2))
         print("\n--- Valores Secretos (Ejemplo Acceso) ---")
         print(f"Telegram Token: {'******' if settings.TELEGRAM_BOT_TOKEN else 'None'}")
         print(f"Kelly API Key: {'******' if settings.API_ACCESS_KEY else 'None'}")
         if settings.MONGO_URI: print(f"Mongo URI: {'******'}")
         print(f"Authorized Debug IDs: {settings.authorized_debug_user_ids}")
    else:
         print("La instancia 'settings' no pudo ser creada.")