from fastapi import APIRouter, Response

from app.services import badge

router = APIRouter()


@router.get("/badge/{package_name}.svg")
async def get_badge(package_name: str, score: str = "safety") -> Response:
    svg = await badge.build_badge_svg(package_name, score_type=score)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            # Short browser cache, longer CDN/proxy cache (e.g. GitHub's camo
            # image proxy) - badges don't need to be second-fresh, and the
            # service-level cache in badge.py already bounds live scans to
            # one per package per 6h regardless of how often this is hit.
            "Cache-Control": "public, max-age=3600, s-maxage=21600",
        },
    )
