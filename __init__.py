# ============================================================================ #
#  CANVAS LOCK - Aspect ratio lock for Blender's render resolution
# ============================================================================ #
#  A tiny quality-of-life add-on: adds a lock toggle to Blender's native
#  Format panel. With the lock on, changing Resolution X or Y automatically
#  adjusts the other one to keep the aspect ratio. Includes a one-click
#  orientation swap (portrait/landscape).
#
#  Free extract from "Open Canvas", a full framing & format suite:
#  physical sizes (cm/in + DPI), overscan without changing perspective,
#  viewport guides, print bleed and automatic DPI metadata.
#
#  Author: Ricardo Rey (Teteerck) - License: GPL-3.0-or-later
# ============================================================================

import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty
from bpy.types import Operator, PropertyGroup
from bpy.app.handlers import persistent


# ============================================================================ #
#  STATE
# ============================================================================ #

# Guard so our own programmatic writes don't re-trigger the lock
_guard = {"busy": False}

_msgbus_owner = object()


# ============================================================================ #
#  LOCK LOGIC (msgbus listens to Blender's native resolution properties)
# ============================================================================ #

def _lock_on_x_change():
    if _guard["busy"]:
        return
    scene = bpy.context.scene
    props = scene.canvas_lock
    if not props.lock_ratio or props.locked_ratio <= 0:
        return
    new_y = max(1, int(round(scene.render.resolution_x / props.locked_ratio)))
    if scene.render.resolution_y != new_y:
        _guard["busy"] = True
        try:
            scene.render.resolution_y = new_y
        finally:
            _guard["busy"] = False


def _lock_on_y_change():
    if _guard["busy"]:
        return
    scene = bpy.context.scene
    props = scene.canvas_lock
    if not props.lock_ratio or props.locked_ratio <= 0:
        return
    new_x = max(1, int(round(scene.render.resolution_y * props.locked_ratio)))
    if scene.render.resolution_x != new_x:
        _guard["busy"] = True
        try:
            scene.render.resolution_x = new_x
        finally:
            _guard["busy"] = False


def subscribe_msgbus():
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.RenderSettings, "resolution_x"),
        owner=_msgbus_owner, args=(), notify=_lock_on_x_change)
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.RenderSettings, "resolution_y"),
        owner=_msgbus_owner, args=(), notify=_lock_on_y_change)


@persistent
def _on_load_post(dummy):
    """msgbus subscriptions are lost when opening a file: re-subscribe."""
    subscribe_msgbus()


def lock_toggle_update(self, context):
    """When the lock is enabled, memorize the current ratio."""
    if self.lock_ratio:
        r = context.scene.render
        if r.resolution_y > 0:
            self.locked_ratio = r.resolution_x / r.resolution_y


# ============================================================================ #
#  ORIENTATION SWAP
# ============================================================================ #

class CL_OT_swap_orientation(Operator):
    bl_idname = "render.cl_swap_orientation"
    bl_label = "Swap Orientation"
    bl_description = "Swap Resolution X and Y (portrait/landscape)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        props = scene.canvas_lock
        r = scene.render
        _guard["busy"] = True
        try:
            r.resolution_x, r.resolution_y = \
                r.resolution_y, r.resolution_x
            if props.lock_ratio and props.locked_ratio > 0:
                props.locked_ratio = 1.0 / props.locked_ratio
        finally:
            _guard["busy"] = False
        return {'FINISHED'}


# ============================================================================ #
#  PROPERTIES
# ============================================================================ #

class CL_Props(PropertyGroup):
    lock_ratio: BoolProperty(
        name="Lock Aspect Ratio", default=False,
        update=lock_toggle_update,
        description="When you change Resolution X or Y, the other side "
                    "adjusts automatically to keep the current ratio")
    locked_ratio: FloatProperty(default=1.777778, options={'HIDDEN'})


# ============================================================================ #
#  UI (injected into Blender's native Format panel)
# ============================================================================ #

def draw_format_lock(self, context):
    props = context.scene.canvas_lock
    row = self.layout.row(align=True)
    row.prop(props, "lock_ratio",
             icon='LOCKED' if props.lock_ratio else 'UNLOCKED')
    row.operator("render.cl_swap_orientation", text="",
                 icon='FILE_REFRESH')


# ============================================================================ #
#  REGISTRATION
# ============================================================================ #

classes = (
    CL_Props,
    CL_OT_swap_orientation,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.canvas_lock = PointerProperty(type=CL_Props)
    subscribe_msgbus()
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    bpy.types.RENDER_PT_format.append(draw_format_lock)


def unregister():
    bpy.types.RENDER_PT_format.remove(draw_format_lock)
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    bpy.msgbus.clear_by_owner(_msgbus_owner)
    del bpy.types.Scene.canvas_lock
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
