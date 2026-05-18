"""Shared DB engines (read-write and read-only)."""
from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@st.cache_resource
def get_engine() -> Engine:
    """Full-access engine — used for UI reads against owned tables."""
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


@st.cache_resource
def get_readonly_engine() -> Engine:
    """Read-only engine — used to execute LLM-generated SQL safely."""
    return create_engine(os.environ["DATABASE_URL_READONLY"], pool_pre_ping=True)
