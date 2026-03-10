"""AT-SPI helper - query UI element tree and interact with controls."""

import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi
from dataclasses import dataclass


@dataclass
class UIElement:
    """Represents a UI control element."""
    name: str
    role: str
    x: int
    y: int
    width: int
    height: int
    states: list[str]
    actions: list[str]
    value: str | None
    _node: object  # Atspi.Accessible ref

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2

    def __str__(self):
        return f"[{self.role}] '{self.name}' at ({self.x},{self.y} {self.width}x{self.height})"


def _get_states(node) -> list[str]:
    try:
        state_set = node.get_state_set()
        states = []
        for s in dir(Atspi.StateType):
            if s.startswith('_'):
                continue
            try:
                st = getattr(Atspi.StateType, s)
                if state_set.contains(st):
                    states.append(s.lower())
            except Exception:
                pass
        return states
    except Exception:
        return []


def _get_actions(node) -> list[str]:
    try:
        action_iface = node.get_action_iface()
        if not action_iface:
            return []
        return [action_iface.get_action_name(i) for i in range(action_iface.get_n_actions())]
    except Exception:
        return []


def _get_value(node) -> str | None:
    try:
        text_iface = node.get_text_iface()
        if text_iface:
            return text_iface.get_text(0, text_iface.get_character_count())
    except Exception:
        pass
    return None


def _to_element(node) -> UIElement | None:
    try:
        name = node.get_name() or ""
        role = node.get_role_name() or ""
        rect = node.get_extents(Atspi.CoordType.SCREEN)
        return UIElement(
            name=name,
            role=role,
            x=rect.x,
            y=rect.y,
            width=rect.width,
            height=rect.height,
            states=_get_states(node),
            actions=_get_actions(node),
            value=_get_value(node),
            _node=node,
        )
    except Exception:
        return None


def list_applications() -> list[str]:
    """List all applications visible to AT-SPI."""
    desktop = Atspi.get_desktop(0)
    apps = []
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app:
            apps.append(app.get_name() or f"unnamed-{i}")
    return apps


def get_app_windows(app_name: str) -> list[UIElement]:
    """Get all windows for a named application."""
    desktop = Atspi.get_desktop(0)
    windows = []
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if app and (app.get_name() or "").lower() == app_name.lower():
            for j in range(app.get_child_count()):
                win = app.get_child_at_index(j)
                if win:
                    elem = _to_element(win)
                    if elem:
                        windows.append(elem)
    return windows


def find_elements(
    root=None,
    role: str | None = None,
    name: str | None = None,
    max_depth: int = 10,
    visible_only: bool = True,
) -> list[UIElement]:
    """
    Find UI elements matching criteria.
    
    Args:
        root: Starting node (None = desktop)
        role: Filter by role (e.g., 'push button', 'text', 'menu item')
        name: Filter by name (substring match, case-insensitive)
        max_depth: Maximum tree depth to search
        visible_only: Only return visible elements
    """
    if root is None:
        root = Atspi.get_desktop(0)

    results = []
    _search(root, role, name, max_depth, 0, visible_only, results)
    return results


def _search(node, role, name, max_depth, depth, visible_only, results):
    if depth > max_depth:
        return

    try:
        elem = _to_element(node)
        if elem:
            match = True
            if role and elem.role.lower() != role.lower():
                match = False
            if name and name.lower() not in elem.name.lower():
                match = False
            if visible_only and "visible" not in elem.states and "showing" not in elem.states:
                match = False
            if match and (role or name):  # Only add if we're actually filtering
                results.append(elem)

        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if child:
                _search(child, role, name, max_depth, depth + 1, visible_only, results)
    except Exception:
        pass


def do_action(element: UIElement, action_name: str = "click") -> bool:
    """Execute an action on a UI element."""
    try:
        action_iface = element._node.get_action_iface()
        if not action_iface:
            return False
        for i in range(action_iface.get_n_actions()):
            if action_iface.get_action_name(i) == action_name:
                return action_iface.do_action(i)
        return False
    except Exception:
        return False


def set_text(element: UIElement, text: str) -> bool:
    """Set text content of an editable element."""
    try:
        edit_iface = element._node.get_editable_text_iface()
        if not edit_iface:
            return False
        # Clear existing text
        text_iface = element._node.get_text_iface()
        if text_iface:
            length = text_iface.get_character_count()
            if length > 0:
                edit_iface.delete_text(0, length)
        edit_iface.insert_text(0, text, len(text))
        return True
    except Exception:
        return False


def get_focused_element() -> UIElement | None:
    """Get the currently focused UI element."""
    desktop = Atspi.get_desktop(0)
    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        try:
            # Search for focused element
            focused = _find_focused(app, 0, 8)
            if focused:
                return focused
        except Exception:
            continue
    return None


def _find_focused(node, depth, max_depth):
    if depth > max_depth:
        return None
    elem = _to_element(node)
    if elem and "focused" in elem.states:
        return elem
    try:
        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if child:
                result = _find_focused(child, depth + 1, max_depth)
                if result:
                    return result
    except Exception:
        pass
    return None


def get_ui_tree_summary(app_name: str | None = None, max_depth: int = 5) -> str:
    """
    Get a text summary of the UI tree for AI consumption.
    Compact format with indentation.
    """
    desktop = Atspi.get_desktop(0)
    lines = []

    for i in range(desktop.get_child_count()):
        app = desktop.get_child_at_index(i)
        if not app:
            continue
        name = app.get_name() or ""
        if app_name and app_name.lower() not in name.lower():
            continue
        lines.append(f"📱 {name}")
        _tree_summary(app, 1, max_depth, lines)

    return "\n".join(lines)


def _tree_summary(node, depth, max_depth, lines):
    if depth > max_depth:
        return
    try:
        for i in range(node.get_child_count()):
            child = node.get_child_at_index(i)
            if not child:
                continue
            elem = _to_element(child)
            if not elem:
                continue
            # Skip invisible/tiny elements
            if elem.width <= 0 or elem.height <= 0:
                continue

            indent = "  " * depth
            info = f"{indent}[{elem.role}]"
            if elem.name:
                info += f" '{elem.name}'"
            if elem.actions:
                info += f" (actions: {','.join(elem.actions)})"
            if elem.value:
                info += f" value='{elem.value[:50]}'"
            lines.append(info)

            _tree_summary(child, depth + 1, max_depth, lines)
    except Exception:
        pass
