"""Utility helpers for profile and user-agent management."""

from typing import List
from botasaurus.profiles import Profiles
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem


def set_profile(profile: str) -> str:
    """Ensure a botasaurus profile exists with a UA and return the UA.

    - If the profile is not present, a random but constrained user-agent is generated
      (favoring Edge for better rewards results) and stored under the profile.
    - Returns the user-agent string for the profile.
    """
    prof = Profiles.get_profile(profile)
    if not prof:
        # Focar no EDGE para melhores pontos no Rewards
        software_names = [SoftwareName.EDGE.value]
        operating_systems = [
            OperatingSystem.WINDOWS.value,
            OperatingSystem.LINUX.value,
            OperatingSystem.CHROMEOS.value,
            OperatingSystem.MACOS.value,
        ]

        user_agent = (
            UserAgent(
                limit=100,
                operating_systems=operating_systems,
                software_names=software_names,
            ).get_random_user_agent()
        )
        Profiles.set_profile(profile, {"UA": user_agent})
        return user_agent
    return prof["UA"]


def build_user_agent_args(profile: str) -> List[str]:
    """Return browser `add_arguments` for the profile's UA.

    Ensures the profile exists via `set_profile` and returns
    a list to be used with botasaurus `add_arguments`.
    """
    ua = set_profile(profile)
    return [f"--user-agent={ua}"]
