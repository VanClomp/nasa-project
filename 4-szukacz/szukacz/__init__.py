"""Szukacz: silnik wyszukiwania ziemskich analogów (komponent 4)."""

from .data import K_FEATURES, EarthData, load_earth_data
from .engine import search

__all__ = ["K_FEATURES", "EarthData", "load_earth_data", "search"]
