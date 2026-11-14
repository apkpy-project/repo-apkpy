# The Cape Road and the lighthouse.

trainer tess
    before:
        say Halt! Road's closed to anyone who can't fight.
    won:
        give money 50
    after:
        say Road's open. The reeds aren't friendly, though.

trainer bram
    before:
        say So you are Ona's new pet. That lighthouse should have been mine.
        say Let's see what your partner can do.
    won:
        say Go on, then. See if the door opens for you.
    after:
        say Don't look at me. Go and light it.

event route.knot
    say A knot, half buried in the sand.
    give true_knot
    set found_knot

event route.sign
    say CAPE ROAD. Keep to the path. The reeds keep what they find.

event route.lighthouse
    if beat_bram:
        say You push the Keeper's letter under the door.
        say Far above you, something clicks. Then, slowly, a light.
        say The sea, somewhere out in the dark, turns over in its sleep.
        say END OF THE TEMPLATE. Your game starts here.
        set lit
    otherwise:
        say The door is shut. Somebody on the road may know more.
