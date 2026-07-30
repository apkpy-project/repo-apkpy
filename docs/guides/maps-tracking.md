---
title: Maps and continuous location
description: Use explicit Preview routes and real fused Android location without leaking a developer location.
---

# Maps and continuous location

The desktop Previewer has no phone GPS. Give it an explicit fictional route so
the interface can be tested. Android ignores that simulation and uses device
location after permission is granted.

```python
from apkpy_lib import Screen, declare_permissions, location, map_view, run

declare_permissions([
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.ACCESS_BACKGROUND_LOCATION",
])
tracking = Screen(id="tracking")

preview_route = [
    {"lat": 40.7484, "lng": -73.9857},
    {"lat": 40.7492, "lng": -73.9838},
    {"lat": 40.7501, "lng": -73.9821},
]

map_panel = map_view(
    markers=[],
    route=preview_route,
    show_user=True,
    follow_user=True,
    screen=tracking,
)

def position_changed(success, lat, lng, accuracy, speed):
    if success:
        map_panel.set_location(lat, lng, accuracy)

location.watch(
    "courier",
    on_update=position_changed,
    interval=1500,
    min_distance=3,
    preview_route=preview_route,
    screen=tracking,
)

run(tracking)
```

For a road-aware path, call `routes.calculate(...)` only after the user asks
for a route, decode it with `route_points(...)`, then pass the result to
`map_panel.set_route(...)`.

## Privacy and lifecycle

- do not infer a developer location in the Previewer;
- explain why foreground or background location is needed;
- stop watchers when tracking ends;
- expect indoor accuracy to be lower;
- test process recreation and Android background restrictions;
- treat route services as external network processors in your privacy policy.
