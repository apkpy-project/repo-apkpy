# The start of the game, the village and the Keeper's house.
# How to write this: see the top of tools/story_tool.py.

event intro
    say The tide went out nine days ago.
    say It did not come back.
    say You came to Saltmere on the last boat, to be apprentice to the Keeper of the lighthouse.
    say The Keeper's house is the one with the red roof. Better not keep her waiting.

event village.gate
    say Reeds grow wild past this point, and the creatures in them bite.
    say Nobody walks the road without a partner. Ask the Keeper.
    step_back

event village.vendor
    say Harbour stall. Everything is half salt, but it works.
    shop harbour

event village.villager
    once gift_knots:
        say A new Warden? Take these. A knot only holds on something tired.
        give bond_knot 5
        give tonic 3
    otherwise:
        say Wear them down first. Then the knot.

event village.sign
    say SALTMERE. North: Cape Road and the lighthouse.

event village.locked
    say Locked. The owner is at the stall.

event house.keeper
    once got_partner:
        say So you are the one they sent. I am Ona. I kept the light for forty years.
        say Driftlings came in with the last tide, and they will not leave an unlit shore. So we need the light.
        say Nobody walks the Cape alone. Choose one: it will choose you back, in time.
        open starter
        give keeper_letter
        say Take this letter to the lighthouse door. And mind Bram, on the road. He thinks the job was his.
    otherwise:
        ask Tired? Sleep here a while.
        yes:
            heal
            say You wake up rested. Your partners too.
        no:
            say Go on, then.
