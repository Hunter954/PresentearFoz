"""Shared defaults and validation for catalog options."""
import re
import uuid

METHOD_LABELS = {"laser": "Gravação a laser", "sublimation": "Sublimação"}
PALETTE = [
    ("branco", "Branco", "#FFFFFF"), ("preto", "Preto", "#202124"),
    ("azul", "Azul", "#2864B4"), ("azul-marinho", "Azul-marinho", "#243563"),
    ("vermelho", "Vermelho", "#C83F44"), ("rosa", "Rosa", "#E9A4B5"),
    ("verde", "Verde", "#368469"), ("amarelo", "Amarelo", "#F1CE43"),
    ("laranja", "Laranja", "#E9873F"), ("roxo", "Roxo", "#8464A2"),
    ("cinza", "Cinza", "#9CA3AF"), ("prata", "Prata", "#C9CDD2"),
    ("dourado", "Dourado", "#C5A15A"),
]


def default_colors():
    # image_path is reserved for future color-specific photography.
    return [dict(id=key, name=name, hex=hex_value, image_path=None) for key, name, hex_value in PALETTE]


def parse_colors(form, existing):
    ids, names, values = (form.getlist(key) for key in ("color_id", "color_name", "color_hex"))
    if not len(ids) == len(names) == len(values) or len(ids) > 50:
        raise ValueError("Envie até 50 cores com nome e tonalidade.")
    previous = {color["id"]: color for color in (existing or [])}
    colors, seen_ids, seen_names = [], set(), set()
    for key, name, value in zip(ids, names, values):
        name = name.strip()
        if not name or len(name) > 60 or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Cada cor precisa de um nome (até 60 caracteres) e uma tonalidade válida.")
        if name.casefold() in seen_names:
            raise ValueError("Não repita o nome de uma cor no mesmo produto.")
        key = key if key in previous else uuid.uuid4().hex
        if key in seen_ids:
            raise ValueError("Cor duplicada. Atualize a página e tente novamente.")
        colors.append(dict(id=key, name=name, hex=value.upper(), image_path=previous.get(key, {}).get("image_path")))
        seen_ids.add(key)
        seen_names.add(name.casefold())
    return colors
