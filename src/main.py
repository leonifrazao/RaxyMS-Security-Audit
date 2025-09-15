from resources import *

profile = "jhasdjhkashjk"
returned_profile = set_profile(profile)
print(returned_profile)
# login(profile=profile, add_arguments=[f'--user-agent={returned_profile}'])

# goto_rewards_page(profile=profile, add_arguments=[f'--user-agent={returned_profile}'])