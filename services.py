from fastmcp import FastMCP
from pypco import PCO
import os
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("PCO Services MCP Server")

pco = PCO(
    application_id=os.getenv("PCO_APPLICATION_ID"),
    secret=os.getenv("PCO_SECRET_KEY")
)


def _iterate_all(endpoint: str, **params) -> list:
    """
    Iterate through all pages of results from a PCO endpoint.
    Uses pypco's iterate() which transparently handles pagination.

    Args:
        endpoint: API endpoint path (e.g., '/services/v2/songs')
        **params: Query parameters to pass to the API

    Returns:
        list: All items from all pages
    """
    results = []
    for item in pco.iterate(endpoint, **params):
        results.append(item['data'])
    return results


def _get_all_song_tags() -> list:
    """
    Get all song tags from all tag groups with pagination.

    Returns:
        list: Flat list of all Tag objects for songs
    """
    all_tags = []
    for tag_group in pco.iterate('/services/v2/tag_groups', filter='song'):
        tag_group_id = tag_group['data']['id']
        for tag in pco.iterate(f'/services/v2/tag_groups/{tag_group_id}/tags'):
            all_tags.append(tag['data'])
    return all_tags


@mcp.tool()
def get_service_types() -> list:
    """
    Fetch all service types from Planning Center Online.
    Returns all service types, handling pagination automatically.
    """
    return _iterate_all('/services/v2/service_types')


@mcp.tool()
def get_plans(service_type_id: str) -> list:
    """
    Fetch all plans for a specific service type.
    Returns all plans ordered by most recently updated, handling pagination automatically.

    Args:
        service_type_id: The ID of the service type.
    """
    return _iterate_all(
        f'/services/v2/service_types/{service_type_id}/plans',
        order='-updated_at'
    )


@mcp.tool()
def get_plan_items(plan_id: str) -> list:
    """
    Fetch all items for a specific plan.
    Returns all items, handling pagination automatically.

    Args:
        plan_id: The ID of the plan.
    """
    return _iterate_all(f'/services/v2/plans/{plan_id}/items')


@mcp.tool()
def get_plan_team_members(plan_id: str) -> list:
    """
    Fetch all team members for a specific plan.
    Returns all team members, handling pagination automatically.

    Args:
        plan_id: The ID of the plan.
    """
    return _iterate_all(f'/services/v2/plans/{plan_id}/team_members')


@mcp.tool()
def get_songs() -> list:
    """
    Fetch all non-hidden songs from Planning Center Online.
    Returns all songs, handling pagination automatically.
    """
    return _iterate_all('/services/v2/songs', **{'where[hidden]': 'false'})


@mcp.tool()
def get_all_arrangements_for_song(song_id: str) -> list:
    """
    Get all arrangements for a particular song.
    Returns all arrangements, handling pagination automatically.

    Args:
        song_id: The ID for the song.
    """
    return _iterate_all(f'/services/v2/songs/{song_id}/arrangements')


@mcp.tool()
def get_arrangement_for_song(song_id: str, arrangement_id: str) -> list:
    """
    Get information for a specific arrangement of a song.

    Args:
        song_id: The ID for the song.
        arrangement_id: The ID for the arrangement within a song.
    """
    response = pco.get(f'/services/v2/songs/{song_id}/arrangements/{arrangement_id}')
    return response['data']


@mcp.tool()
def get_keys_for_arrangement_of_song(song_id: str, arrangement_id: str) -> list:
    """
    Get all available keys for a specific song arrangement.

    Args:
        song_id: The ID for the song.
        arrangement_id: The ID for the arrangement within a song.
    """
    response = pco.get(f'/services/v2/songs/{song_id}/arrangements/{arrangement_id}/keys')
    return response['data']


@mcp.tool()
def create_song(title: str, ccli: str = None) -> dict:
    """
    Create a new song in Planning Center Online.

    Args:
        title: The title of the song.
        ccli: The CCLI number for the song (optional).

    Returns:
        dict: The created song data.
    """
    attributes = {"title": title}
    if ccli:
        attributes["ccli_number"] = ccli

    body = pco.template('Song', attributes)
    response = pco.post('/services/v2/songs', body)
    return response['data']


@mcp.tool()
def find_song_by_title(title: str) -> list:
    """
    Find songs by title.
    Returns all matching non-hidden songs, handling pagination automatically.

    Args:
        title: The title of the song to search for.

    Returns:
        list: List of songs matching the title.
    """
    return _iterate_all(
        '/services/v2/songs',
        **{'where[title]': title, 'where[hidden]': 'false'}
    )


@mcp.tool()
def get_song(song_id: str) -> dict:
    """
    Fetch details for a specific song.

    Args:
        song_id: The ID of the song.
    """
    response = pco.get(f'/services/v2/songs/{song_id}')
    return response['data']


@mcp.tool()
def assign_tags_to_song(song_id: str, tag_names: list[str]) -> dict:
    """
    Assign tags to a specific song.

    Args:
        song_id: The ID of the song.
        tag_names: List of tag names to assign to the song.

    Returns:
        dict: Success status and message.
    """
    all_tags = _get_all_song_tags()

    tag_data = []
    for tag_name in tag_names:
        for tag in all_tags:
            if tag['attributes']['name'].lower() == tag_name.lower():
                tag_data.append({
                    "type": "Tag",
                    "id": tag['id']
                })
                break

    if not tag_data:
        return {"success": False, "message": "No matching tags found"}

    body = {
        "data": {
            "type": "TagAssignment",
            "attributes": {},
            "relationships": {
                "tags": {
                    "data": tag_data
                }
            }
        }
    }

    pco.post(f'/services/v2/songs/{song_id}/assign_tags', body)
    return {"success": True, "message": f"Successfully assigned {len(tag_data)} tag(s) to song {song_id}"}


@mcp.tool()
def find_songs_by_tags(tag_names: list[str]) -> list:
    """
    Find songs that have all of the specified tags.
    Returns all matching non-hidden songs, handling pagination automatically.

    Args:
        tag_names: List of tag names to filter songs by. Songs must have all specified tags.
    """
    all_tags = _get_all_song_tags()

    tag_ids = []
    for tag_name in tag_names:
        for tag in all_tags:
            if tag['attributes']['name'].lower() == tag_name.lower():
                tag_ids.append(tag['id'])
                break

    if not tag_ids:
        return []

    tag_filters = '&'.join([f'where[song_tag_ids]={tag_id}' for tag_id in tag_ids])
    endpoint = f'/services/v2/songs?{tag_filters}'

    return _iterate_all(endpoint, **{'where[hidden]': 'false'})


@mcp.tool()
def get_series() -> list:
    """
    Fetch all series from Planning Center Online.
    Returns all series, handling pagination automatically.
    """
    return _iterate_all('/services/v2/series')


@mcp.tool()
def get_series_by_id(series_id: str) -> dict:
    """
    Fetch details for a specific series.

    Args:
        series_id: The ID of the series.
    """
    response = pco.get(f'/services/v2/series/{series_id}')
    return response['data']


@mcp.tool()
def get_series_artwork(series_id: str) -> dict:
    """
    Fetch artwork URLs for a specific series.
    Returns series data including artwork URLs in various sizes (thumbnail, medium, original).

    Args:
        series_id: The ID of the series.
    """
    response = pco.get(f'/services/v2/series/{series_id}')
    return response['data']
