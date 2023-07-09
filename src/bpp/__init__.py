from crispy_forms import layout

default_app_config = "bpp.apps.BppConfig"
import asgiref

from . import monkey_patches

# Monkey Patches
asgiref.sync.sync_to_async = monkey_patches.patch_sync_to_async
layout.BaseInput.render = monkey_patches.fix_crispy_forms_BaseInput_render
