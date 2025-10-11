#!/usr/bin/env python3
"""
Filename Handler - Simple filename generator using original functions
"""

from ..filename_components import build_ordered_components


class SimpleFilenameGenerator:
    """Simple filename generator using original functions"""
    
    def __init__(self):
        pass
    
    def generate_filename(self, date_taken, camera_prefix, additional, camera_model, lens_model, 
                         use_camera, use_lens, num, custom_order, date_format="YYYY-MM-DD", use_date=True):
        components = build_ordered_components(
            date_taken=date_taken,
            camera_prefix=camera_prefix,
            additional=additional,
            camera_model=camera_model,
            lens_model=lens_model,
            use_camera=use_camera,
            use_lens=use_lens,
            number=num,
            custom_order=custom_order,
            date_format=date_format,
            use_date=use_date,
            selected_metadata=None,
        )
        return components
