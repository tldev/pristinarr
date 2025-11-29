"""Base Starr API client for Lidarr, Radarr, Readarr, and Sonarr."""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class StarrAPIError(Exception):
    """Exception raised for Starr API errors."""

    def __init__(self, status_code: int, message: str, application: str):
        self.status_code = status_code
        self.message = message
        self.application = application
        super().__init__(f"{application} API error ({status_code}): {message}")


class StarrClient:
    """API client for Starr applications (Lidarr, Radarr, Readarr, Sonarr)."""

    def __init__(
        self,
        app_type: str,
        url: str,
        api_key: str,
        api_version: Optional[str] = None,
    ):
        """Initialize the Starr client.

        Args:
            app_type: Type of application (radarr, sonarr, lidarr, readarr).
            url: Base URL of the application.
            api_key: API key for authentication.
            api_version: API version (e.g., 'v3'). If None, will be fetched.
        """
        self.app_type = app_type.lower()
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.api_version = api_version
        
        self._client = httpx.AsyncClient(
            headers={"X-Api-Key": api_key},
            timeout=30.0,
        )

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def _check_response(self, response: httpx.Response, operation: str) -> None:
        """Check the API response and raise appropriate errors.

        Args:
            response: The HTTP response object.
            operation: Name of the operation being performed.

        Raises:
            StarrAPIError: If the response indicates an error.
        """
        status_code = response.status_code

        if 200 <= status_code < 300:
            return

        error_messages = {
            302: "Redirect - are you missing the URL base?",
            400: "Bad Request - please check your configuration",
            401: "Unauthorized - please check your API key",
            404: "Not Found - please check your configuration",
            409: "Conflict - please check your configuration",
            500: "Internal Server Error - check the application logs",
        }

        message = error_messages.get(
            status_code,
            f"Unexpected HTTP status code {status_code}",
        )

        raise StarrAPIError(status_code, message, self.app_type)

    async def get_api_version(self) -> str:
        """Get the current API version from the application.

        Returns:
            The API version string (e.g., 'v3').
        """
        response = await self._client.get(f"{self.url}/api")
        self._check_response(response, "get_api_version")
        
        data = response.json()
        version = data.get("current", "v3")
        logger.debug(f"API version for {self.app_type}: {version}")
        
        return version

    async def get_media(self) -> list[dict[str, Any]]:
        """Get all media items from the application.

        Returns:
            List of media objects (movies, series, artists, or authors).
        """
        endpoint = self._get_media_endpoint()
        response = await self._client.get(
            f"{self.url}/api/{self.api_version}/{endpoint}"
        )
        self._check_response(response, "get_media")
        
        return response.json()

    def _get_media_endpoint(self) -> str:
        """Get the API endpoint for media based on app type."""
        endpoints = {
            "radarr": "movie",
            "sonarr": "series",
            "lidarr": "artist",
            "readarr": "author",
        }
        return endpoints.get(self.app_type, "movie")

    def _get_editor_endpoint(self) -> str:
        """Get the API endpoint for editor operations."""
        endpoints = {
            "radarr": "movie/editor",
            "sonarr": "series/editor",
            "lidarr": "artist/editor",
            "readarr": "author/editor",
        }
        return endpoints.get(self.app_type, "movie/editor")

    def _get_media_id_field(self) -> str:
        """Get the field name for media IDs in API requests."""
        fields = {
            "radarr": "movieIds",
            "sonarr": "seriesIds",
            "lidarr": "artistIds",
            "readarr": "authorIds",
        }
        return fields.get(self.app_type, "movieIds")

    def _get_search_command_name(self) -> str:
        """Get the command name for searching."""
        commands = {
            "radarr": "MoviesSearch",
            "sonarr": "SeriesSearch",
            "lidarr": "ArtistSearch",
            "readarr": "AuthorSearch",
        }
        return commands.get(self.app_type, "MoviesSearch")

    def _get_search_id_field(self) -> str:
        """Get the field name for search ID in commands."""
        # Note: Sonarr/Lidarr/Readarr use singular form
        fields = {
            "radarr": "movieIds",
            "sonarr": "seriesId",
            "lidarr": "artistId",
            "readarr": "authorId",
        }
        return fields.get(self.app_type, "movieIds")

    async def get_tags(self) -> list[dict[str, Any]]:
        """Get all tags from the application.

        Returns:
            List of tag objects with 'id' and 'label'.
        """
        response = await self._client.get(
            f"{self.url}/api/{self.api_version}/tag"
        )
        self._check_response(response, "get_tags")
        
        return response.json()

    async def get_tag_id(self, tag_name: str) -> Optional[int]:
        """Get the ID of a tag by name.

        Args:
            tag_name: Name of the tag to find.

        Returns:
            The tag ID, or None if not found.
        """
        tags = await self.get_tags()
        
        for tag in tags:
            if tag.get("label", "").lower() == tag_name.lower():
                return tag["id"]
        
        return None

    async def create_tag(self, tag_name: str) -> int:
        """Create a new tag.

        Args:
            tag_name: Name of the tag to create.

        Returns:
            The ID of the newly created tag.
        """
        response = await self._client.post(
            f"{self.url}/api/{self.api_version}/tag",
            json={"label": tag_name},
        )
        self._check_response(response, "create_tag")
        
        data = response.json()
        logger.info(f"Created tag '{tag_name}' with ID {data['id']} in {self.app_type}")
        
        return data["id"]

    async def get_or_create_tag(self, tag_name: str) -> int:
        """Get a tag ID, creating the tag if it doesn't exist.

        Args:
            tag_name: Name of the tag.

        Returns:
            The tag ID.
        """
        tag_id = await self.get_tag_id(tag_name)
        
        if tag_id is None:
            logger.warning(
                f"Tag '{tag_name}' does not exist in {self.app_type}, creating it now"
            )
            tag_id = await self.create_tag(tag_name)
        
        return tag_id

    async def get_quality_profiles(self) -> list[dict[str, Any]]:
        """Get all quality profiles from the application.

        Returns:
            List of quality profile objects.
        """
        response = await self._client.get(
            f"{self.url}/api/{self.api_version}/qualityprofile"
        )
        self._check_response(response, "get_quality_profiles")
        
        return response.json()

    async def get_quality_profile_id(self, profile_name: str) -> int:
        """Get the ID of a quality profile by name.

        Args:
            profile_name: Name of the quality profile.

        Returns:
            The quality profile ID.

        Raises:
            ValueError: If the profile doesn't exist.
        """
        profiles = await self.get_quality_profiles()
        
        for profile in profiles:
            if profile.get("name", "").lower() == profile_name.lower():
                return profile["id"]
        
        raise ValueError(
            f"Quality Profile '{profile_name}' does not exist in {self.app_type}"
        )

    async def add_media_tag(
        self,
        media: list[dict[str, Any]],
        tag_id: int,
    ) -> None:
        """Add a tag to media items.

        Args:
            media: List of media objects.
            tag_id: ID of the tag to add.
        """
        if not media:
            return

        media_ids = [item["id"] for item in media]
        endpoint = self._get_editor_endpoint()
        id_field = self._get_media_id_field()

        body = {
            id_field: media_ids,
            "tags": [tag_id],
            "applyTags": "add",
        }

        response = await self._client.put(
            f"{self.url}/api/{self.api_version}/{endpoint}",
            json=body,
        )
        self._check_response(response, "add_media_tag")
        
        logger.info(f"Added tag to {len(media)} media items in {self.app_type}")

    async def remove_media_tag(
        self,
        media: list[dict[str, Any]],
        tag_id: int,
    ) -> None:
        """Remove a tag from media items.

        Args:
            media: List of media objects.
            tag_id: ID of the tag to remove.
        """
        if not media:
            return

        media_ids = [item["id"] for item in media]
        endpoint = self._get_editor_endpoint()
        id_field = self._get_media_id_field()

        body = {
            id_field: media_ids,
            "tags": [tag_id],
            "applyTags": "remove",
        }

        response = await self._client.put(
            f"{self.url}/api/{self.api_version}/{endpoint}",
            json=body,
        )
        self._check_response(response, "remove_media_tag")
        
        logger.info(f"Removed tag from {len(media)} media items in {self.app_type}")

    async def search_media(self, media: list[dict[str, Any]]) -> None:
        """Start a search for media items.

        Args:
            media: List of media objects to search.
        """
        if not media:
            return

        command_name = self._get_search_command_name()
        id_field = self._get_search_id_field()

        # Radarr supports batch search, others need individual calls
        if self.app_type == "radarr":
            media_ids = [item["id"] for item in media]
            body = {
                "name": command_name,
                id_field: media_ids,
            }
            response = await self._client.post(
                f"{self.url}/api/{self.api_version}/command",
                json=body,
            )
            self._check_response(response, "search_media")
        else:
            # Sonarr, Lidarr, Readarr need individual calls
            for item in media:
                body = {
                    "name": command_name,
                    id_field: item["id"],
                }
                response = await self._client.post(
                    f"{self.url}/api/{self.api_version}/command",
                    json=body,
                )
                self._check_response(response, "search_media")

        logger.info(f"Started search for {len(media)} items in {self.app_type}")

    def filter_media(
        self,
        media: list[dict[str, Any]],
        tag_id: int,
        monitored: bool = True,
        status: Optional[str] = None,
        quality_profile_id: Optional[int] = None,
        ignore_tag_id: Optional[int] = None,
        unattended: bool = False,
    ) -> list[dict[str, Any]]:
        """Filter media based on criteria.

        Args:
            media: List of all media objects.
            tag_id: ID of the tag to filter by.
            monitored: Filter by monitored status.
            status: Filter by status (movie/series/artist/author status).
            quality_profile_id: Filter by quality profile ID.
            ignore_tag_id: Tag ID to exclude from results.
            unattended: If True, return media WITH the tag; if False, WITHOUT.

        Returns:
            Filtered list of media objects.
        """
        filtered = []

        for item in media:
            # Check monitored status
            if item.get("monitored") != monitored:
                continue

            # Check tag presence
            item_tags = item.get("tags", [])
            
            if unattended:
                # In unattended mode, we want media WITH the tag
                if tag_id not in item_tags:
                    continue
            else:
                # Normal mode, we want media WITHOUT the tag
                if tag_id in item_tags:
                    continue

            # Check status if specified
            if status:
                item_status = item.get("status", "").lower()
                if item_status != status.lower():
                    continue

            # Check quality profile if specified
            if quality_profile_id is not None:
                if item.get("qualityProfileId") != quality_profile_id:
                    continue

            # Check ignore tag if specified (only in normal mode)
            if not unattended and ignore_tag_id is not None:
                if ignore_tag_id in item_tags:
                    continue

            filtered.append(item)

        return filtered

