from botasaurus.profiles import Profiles
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem

def set_profile(profile: str):
    prof = Profiles.get_profile(profile)
    if not prof:
        # software_names = [SoftwareName.CHROME.value, SoftwareName.EDGE.value, SoftwareName.FIREFOX.value, SoftwareName.OPERA.value, SoftwareName.VIVALDI.value, SoftwareName.WATERFOX.value]
        # É melhor deixar somente o EDGE por + pontos
        software_names = [SoftwareName.EDGE.value]
        operating_systems = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value, OperatingSystem.CHROMEOS.value, OperatingSystem.MACOS.value]  
        
        user_agent = UserAgent(limit=100, operating_systems=operating_systems, software_names=software_names).get_random_user_agent()
        Profiles.set_profile(profile, {'UA': user_agent})
        return user_agent
    return prof["UA"]