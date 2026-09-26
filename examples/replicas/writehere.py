"""Four apps you know, rebuilt with ApkPy.

A chat list and a conversation you can type into, a music app's home and a
player that really plays, a photo feed -- every post a row built from
components, with a heart that turns red -- its stories and camera, and a ride
sheet over a map. Every name, picture and sound in them is made up.

Run ``python make_assets.py`` once first: it draws the covers, faces, photos
and stories, and writes three short tracks, next to this file. Then
``apkpy preview`` or ``apkpy run``.
"""
from apkpy_lib import *

home = Screen(id="home", scroll=True)
msg_list = Screen(id="msg_list")
msg_chat = Screen(id="msg_chat")
mu_home = Screen(id="mu_home", scroll=True)
mu_player = Screen(id="mu_player")
ph_feed = Screen(id="ph_feed")
ph_story = Screen(id="ph_story")
ph_camera = Screen(id="ph_camera")
ride = Screen(id="ride")

# ── Home ────────────────────────────────────────────────────────────────────
label("Replicas", id="home_title", screen=home)
label("Four apps, rebuilt with ApkPy.", id="home_copy", screen=home)
button("Chat", id="go_chat", icon="chat", screen=home,
       command=lambda: on_click_navigate(msg_list))
button("Music", id="go_music", icon="library_music", screen=home,
       command=lambda: on_click_navigate(mu_home))
button("Photos", id="go_photos", icon="photo_camera", screen=home,
       command=lambda: on_click_navigate(ph_feed))
button("Ride", id="go_ride", icon="directions_car", screen=home,
       command=lambda: on_click_navigate(ride))


# ── Chat: the list ──────────────────────────────────────────────────────
def msg_header(title, screen):
    bar = container(id="msg_bar", screen=screen)
    label(title, id="msg_brand", parent=bar)
    container(id="msg_spacer", parent=bar)
    button("", id="msg_cam", icon="photo_camera", describe="Camera", parent=bar,
           command=lambda: on_click_navigate(ph_camera))
    button("", id="msg_more", icon="more_vert", describe="More", parent=bar,
           command=lambda: toast("Settings"))


msg_header("Chats", msg_list)
inputs("Search", id="msg_search", screen=msg_list)
chips = container(id="msg_chips", screen=msg_list)
button("All", id="msg_chip_on", parent=chips, command=lambda: toast("All"))
button("Unread 3", id="msg_chip", parent=chips, command=lambda: toast("Unread"))
button("Groups", id="msg_chip2", parent=chips, command=lambda: toast("Groups"))


def open_chat(item):
    chat_name.set_value(item["name"])
    on_click_navigate(msg_chat)


chats = virtual_collection(
    [
        {"name": "Mara Vale", "last": "Yes! 8pm at Barr", "time": "21:42", "unread": "2"},
        {"name": "Liv Moreau", "last": "Photo", "time": "20:15", "unread": ""},
        {"name": "Family", "last": "Mum: Dinner on Sunday?", "time": "19:03", "unread": "5"},
        {"name": "Theo Park", "last": "Sent you the tickets", "time": "Yesterday", "unread": ""},
        {"name": "Running club", "last": "Ana: 7am at the park", "time": "Yesterday", "unread": ""},
        {"name": "Nell Shore", "last": "Thank you!!", "time": "Monday", "unread": ""},
    ],
    template={"avatar": "{name}", "title": "{name}", "subtitle": "{last}",
              "meta": "{time}", "badge": "{unread}"},
    id="msg_chats", item_height="auto", on_click=open_chat, screen=msg_list,
)
button("", id="msg_fab", icon="add_comment", describe="New chat", screen=msg_list,
       command=lambda: toast("New chat"))

# ── Chat: a conversation ─────────────────────────────────────────────────
head = container(id="chat_head", screen=msg_chat)
button("", id="chat_back", icon="arrow_back", describe="Back", parent=head,
       command=lambda: on_click_navigate(msg_list))
avatar("face1.png", size=40, id="chat_face", parent=head, describe="")
who = container(id="chat_who", parent=head)
chat_name = label("Mara Vale", id="chat_name", parent=who)
label("online", id="chat_status", parent=who)
button("", id="chat_video", icon="videocam", describe="Video call", parent=head,
       command=lambda: toast("Video call"))
button("", id="chat_call", icon="call", describe="Call", parent=head,
       command=lambda: toast("Call"))

thread = virtual_collection(
    [
        {"kind": "day", "text": "TODAY"},
        {"kind": "them", "text": "Are we still on for tonight?", "time": "21:30"},
        {"kind": "read", "text": "Yes! 8pm at Barr", "time": "21:31"},
        {"kind": "them", "text": "Perfect. I booked a table by the window, they have the new tasting menu this week", "time": "21:40"},
        {"kind": "read", "text": "Amazing, see you there", "time": "21:42"},
    ],
    variant="{kind}",
    template={
        "day": {"meta": "{text}"},
        "them": {"subtitle": "{text}", "meta": "{time}"},
        "mine": {"subtitle": "{text}", "meta": "{time} ✓"},
        "read": {"subtitle": "{text}", "meta": "{time} ✓✓"},
    },
    id="thread", item_height="auto", screen=msg_chat,
)

composer = container(id="composer", screen=msg_chat)
pill = container(id="pill", parent=composer)
button("", id="emoji", icon="mood", describe="Emoji", parent=pill,
       command=lambda: toast("Emoji"))
message = inputs("Message", id="message", parent=pill)
button("", id="attach", icon="attach_file", describe="Attach", parent=pill,
       command=lambda: toast("Attach"))


def send():
    text = message.get_value()
    if text == "":
        toast("Type a message")
        return
    stamp = datetime.hour() + ":" + datetime.minute()
    thread.append_items([{"kind": "mine", "text": text, "time": stamp}])
    thread.scroll_to_end()
    message.set_value("")


button("", id="send", icon="send", describe="Send", parent=composer, command=send)

# ── Music: home ──────────────────────────────────────────────────────────────
TRACKS = ["track1.wav", "track2.wav", "track3.wav"]
TITLES = ["Night Drive", "Lisbon Rain", "Neon Bloom"]
ARTISTS = ["Mara Vale", "Signal Club", "Nova"]
ARTS = ["cover1.png", "cover2.png", "cover3.png"]


def play_from(index):
    audio.play_playlist(TRACKS, titles=TITLES, artists=ARTISTS, arts=ARTS, start=index)
    on_click_navigate(mu_player)


label("Good evening", id="mu_title", screen=mu_home)
filters = container(id="mu_filters", screen=mu_home)
button("All", id="mu_chip_on", parent=filters, command=lambda: toast("All"))
button("Music", id="mu_chip", parent=filters, command=lambda: toast("Music"))
button("Podcasts", id="mu_chip2", parent=filters, command=lambda: toast("Podcasts"))
grid(
    [
        {"title": "Night Drive", "subtitle": "Mara Vale", "image": "cover1.png"},
        {"title": "Lisbon Rain", "subtitle": "Signal Club", "image": "cover2.png"},
        {"title": "Neon Bloom", "subtitle": "Nova", "image": "cover3.png"},
        {"title": "Slow Tide", "subtitle": "Playlist", "image": "cover4.png"},
    ],
    id="mu_recent", cols=2, screen=mu_home,
    on_click=lambda item: play_from(0),
)
label("Made for you", id="mu_section", screen=mu_home)
carousel(
    [
        {"title": "Gold Hour", "subtitle": "Mix 1", "image": "cover5.png"},
        {"title": "Static Heart", "subtitle": "Mix 2", "image": "cover6.png"},
        {"title": "Neon Bloom", "subtitle": "New this week", "image": "cover3.png"},
    ],
    id="mu_mixes", screen=mu_home, on_click=lambda item: play_from(1),
)
mini_player(open=mu_player, id="mu_mini")

# ── Music: the player ──────────────────────────────────────────────────────────
top = container(id="np_top", screen=mu_player)
button("", id="np_down", icon="expand_more", describe="Close", parent=top,
       command=lambda: on_click_navigate(mu_home))
label("PLAYING FROM YOUR LIBRARY", id="np_from", parent=top)
button("", id="np_more", icon="more_vert", describe="More", parent=top,
       command=lambda: toast("Share, add to playlist..."))
np_cover = image("cover1.png", id="np_cover", screen=mu_player, describe="")
np_meta = container(id="np_meta", screen=mu_player)
np_names = container(id="np_names", parent=np_meta)
np_title = label("Night Drive", id="np_title", parent=np_names)
np_artist = label("Mara Vale", id="np_artist", parent=np_names)
np_like = button("", id="np_like", icon="favorite_border", describe="Like", parent=np_meta)
audio.like_button(np_like)
np_progress = inputs("", type="range", id="np_progress", screen=mu_player)
np_time = label("0:00 / 0:00", id="np_time", screen=mu_player)
deck = container(id="np_deck", screen=mu_player)
np_shuffle = button("", id="np_shuffle", icon="shuffle", describe="Shuffle", parent=deck)
button("", id="np_prev", icon="skip_previous", describe="Previous", parent=deck,
       command=audio.previous)
np_play = button("", id="np_play", icon="play_arrow", describe="Play", parent=deck)
button("", id="np_next", icon="skip_next", describe="Next", parent=deck,
       command=audio.next)
np_repeat = button("", id="np_repeat", icon="repeat", describe="Repeat", parent=deck)
audio.now_playing(progress=np_progress, time=np_time, cover=np_cover,
                  title=np_title, artist=np_artist)
audio.controls(play_pause=np_play, shuffle=np_shuffle, repeat=np_repeat)

# ── Photos: the feed ────────────────────────────────────────────────────────────────
story = state(1)
seen1 = state(False)
seen2 = state(False)


def open_story():
    story.set(1)
    seen1.set(False)
    seen2.set(False)
    story_img.set_src("story1.jpg")
    on_click_navigate(ph_story)


bar = container(id="ph_bar", screen=ph_feed)
label("Photos", id="ph_brand", parent=bar)
container(id="ph_spacer", parent=bar)
button("", id="ph_heart", icon="favorite_border", describe="Activity", parent=bar,
       command=lambda: toast("Activity"))
button("", id="ph_dm", icon="send", describe="Messages", parent=bar,
       command=lambda: on_click_navigate(msg_list))

tray = container(id="ph_tray", screen=ph_feed)
for face, name in [("face1.png", "Your story"), ("face2.png", "mara"),
                   ("face3.png", "liv"), ("face4.png", "theo"), ("face5.png", "nell")]:
    bubble = container(id="ph_story_cell", parent=tray)
    avatar(face, size=62, id="ph_ring", parent=bubble, describe=name, command=open_story)
    label(name, id="ph_story_name", parent=bubble)


# The feed is data now: every post is a row built from components, the way a
# real app draws the posts its server sends.
POSTS = [
    {"id": "p1", "user": "mara.vale", "place": "Lisbon, Portugal", "face": "face2.png",
     "picture": "post1.jpg", "likes": 1284, "liked": "", "sponsored": "",
     "caption": "Last light over the river", "comments": "View all 48 comments",
     "when": "2 hours ago"},
    {"id": "p2", "user": "liv.moreau", "place": "Costa Nova", "face": "face3.png",
     "picture": "post2.jpg", "likes": 872, "liked": "yes", "sponsored": "",
     "caption": "Stripes and salt", "comments": "View all 12 comments",
     "when": "5 hours ago"},
    {"id": "p3", "user": "northline.travel", "place": "", "face": "face4.png",
     "picture": "story2.jpg", "likes": 3410, "liked": "", "sponsored": "yes",
     "caption": "Sea days, booked in a minute", "comments": "View all 131 comments",
     "when": "Yesterday"},
    {"id": "p4", "user": "nell.shore", "place": "Porto", "face": "face5.png",
     "picture": "story3.jpg", "likes": 96, "liked": "", "sponsored": "",
     "caption": "Late train home", "comments": "View all 4 comments",
     "when": "2 days ago"},
]


def like(item):
    # The heart and the count change on this row only: update_item patches
    # one record by its id, and the row is drawn again from it.
    if item["liked"] == "yes":
        posts.update_item(item["id"], {"liked": "", "likes": int(item["likes"]) - 1})
    else:
        posts.update_item(item["id"], {"liked": "yes", "likes": int(item["likes"]) + 1})


def open_comments(item):
    toast(item["comments"])


def post_row(row):
    head = container(id="ph_post_head", parent=row)
    avatar("{face}", size=34, id="ph_post_face", parent=head, describe="{user}")
    names = container(id="ph_post_names", parent=head)
    label("{user}", id="ph_post_user", parent=names)
    label("{place}", id="ph_post_place", parent=names, visible="{place}")
    label("Sponsored", id="ph_sponsored", parent=names, visible="{sponsored}")
    container(id="ph_spacer3", parent=head)
    button("", id="ph_post_more", icon="more_horiz", describe="More", parent=head,
           command=lambda: toast("More"))
    image("{picture}", id="ph_post_pic", parent=row, aspect_ratio="1:1", describe="")
    actions = container(id="ph_actions", parent=row)
    button("", id="ph_like", icon="favorite_border", active_icon="favorite",
           active="{liked}", describe="Like", parent=actions,
           command=lambda item: like(item))
    button("", id="ph_comment", icon="chat_bubble_outline", describe="Comment", parent=actions,
           command=open_comments)
    button("", id="ph_share", icon="send", describe="Share", parent=actions,
           command=lambda: toast("Share"))
    container(id="ph_spacer2", parent=actions)
    button("", id="ph_save", icon="bookmark_border", describe="Save", parent=actions,
           command=lambda: toast("Saved"))
    label("{likes} likes", id="ph_like_count", parent=row)
    cap = container(id="ph_cap", parent=row)
    label("{user}", id="ph_cap_user", parent=cap)
    label("{caption}", id="ph_cap_text", parent=cap)
    label("{comments}", id="ph_comments", parent=row)
    label("{when}", id="ph_when", parent=row)


posts = virtual_collection(POSTS, row=post_row, id="ph_posts", screen=ph_feed)

nav = container(id="ph_nav", screen=ph_feed)
button("", id="ph_nav_home", icon="home", describe="Home", parent=nav,
       command=lambda: toast("Home"))
button("", id="ph_nav_search", icon="search", describe="Search", parent=nav,
       command=lambda: toast("Search"))
button("", id="ph_nav_add", icon="add_box", describe="New post", parent=nav,
       command=lambda: on_click_navigate(ph_camera))
button("", id="ph_nav_videos", icon="slideshow", describe="Videos", parent=nav,
       command=lambda: toast("Videos"))
button("", id="ph_nav_me", icon="account_circle", describe="Profile", parent=nav,
       command=lambda: toast("Profile"))

# ── Photos: a story ─────────────────────────────────────────────────────────────


def next_story():
    if story.get() == 1:
        story.set(2)
        seen1.set(True)
        story_img.set_src("story2.jpg")
    elif story.get() == 2:
        story.set(3)
        seen2.set(True)
        story_img.set_src("story3.jpg")
    else:
        on_click_navigate(ph_feed)


stage = container(id="st_stage", screen=ph_story)
story_img = image("story1.jpg", id="st_img", parent=stage, describe="Story",
                  command=next_story)
bars = container(id="st_bars", parent=stage)
seg1 = container(id="st_seg_on", parent=bars)
seg2 = container(id="st_seg_on2", parent=bars)
seg2_off = container(id="st_seg_off", parent=bars)
seg3 = container(id="st_seg_off2", parent=bars)
seen1.bind_visibility(seg2, when=True)
seen1.bind_visibility(seg2_off, when=False)
who2 = container(id="st_who", parent=stage)
avatar("face2.png", size=32, id="st_face", parent=who2, describe="")
label("mara  ·  2h", id="st_name", parent=who2)
button("", id="st_close", icon="close", describe="Close", parent=stage,
       command=lambda: on_click_navigate(ph_feed))
label("Tap to see the next story", id="st_hint", parent=stage)

# ── Photos: the camera ──────────────────────────────────────────────────────────────


def shot(ok, path):
    if ok:
        toast("Photo saved")
    else:
        toast("No photo")


cam_stage = container(id="cam_stage", screen=ph_camera)
visor = camera_view(id="visor", parent=cam_stage, lens="back", fit="cover", on_capture=shot)
button("", id="cam_close", icon="close", describe="Close", parent=cam_stage,
       command=lambda: on_click_navigate(ph_feed))
button("", id="shutter", describe="Take photo", parent=cam_stage,
       command=lambda: visor.capture())
button("", id="flip", icon="cameraswitch", describe="Switch camera", parent=cam_stage,
       command=lambda: visor.flip())

# ── Ride ────────────────────────────────────────────────────────────────────────────
area = container(id="ride_area", screen=ride)
map_view(38.7223, -9.1393, 14, id="ride_map", parent=area)
sheet = container(id="ride_sheet", parent=area)
container(id="ride_handle", parent=sheet)
label("Choose a trip", id="ride_title", parent=sheet)


def pick_standard():
    choose.set_value("Choose Standard")


def pick_comfort():
    choose.set_value("Choose Comfort")


def pick_premium():
    choose.set_value("Choose Premium")


list_row("Standard", subtitle="4 min away · 4 seats", icon="directions_car",
         trailing="€8.40", command=pick_standard, id="ride_opt", parent=sheet)
list_row("Comfort", subtitle="6 min away · Newer cars", icon="local_taxi",
         trailing="€10.90", command=pick_comfort, id="ride_opt", parent=sheet)
list_row("Premium", subtitle="9 min away · Leather seats", icon="airport_shuttle",
         trailing="€19.20", command=pick_premium, id="ride_opt", parent=sheet)
choose = button("Choose Standard", id="ride_go", parent=sheet,
                command=lambda: toast("Finding your driver"))

style = """
home { background-color: #FFFFFF; padding: 20px; }
home_title { font-size: 30px; font-weight: bold; color: #111111; }
home_copy { font-size: 15px; color: #555555; margin-bottom: 14px; }
go_chat, go_music, go_photos, go_ride { height: 56px; border-radius: 16px; margin-bottom: 10px;
                                background-color: #111111; color: #FFFFFF; font-size: 16px;
                                text-transform: none; icon-color: #FFFFFF; }

/* Chat */
msg_list { background-color: #0B141A; padding: 0px; }
msg_bar { display: flex; flex-direction: row; align-items: center; padding: 14px 8px 6px 16px;
         background-color: #0B141A; }
msg_brand { font-size: 24px; font-weight: bold; color: #FFFFFF; }
msg_spacer { flex-grow: 1; background-color: #00000000; padding: 0px; }
msg_cam, msg_more, chat_back, chat_video, chat_call {
    width: 48px; height: 48px; background-color: #00000000; icon-color: #E9EDEF; }
msg_search { margin: 4px 14px; background-color: #202C33; color: #E9EDEF; border-width: 0px;
            border-radius: 24px; padding: 12px 18px; placeholder-color: #8696A0; }
msg_chips { display: flex; flex-direction: row; justify-content: flex-start; gap: 8px; padding: 6px 14px;
           background-color: #0B141A; }
msg_chip_on { background-color: #103529; color: #D9FDD3; border-radius: 16px; font-size: 13px;
             text-transform: none; height: 34px; padding: 0px 14px; }
msg_chip, msg_chip2 { background-color: #202C33; color: #8696A0; border-radius: 16px; font-size: 13px;
                    text-transform: none; height: 34px; padding: 0px 14px; }
msg_chats { height: 620px; background-color: #0B141A; item-background-color: #0B141A;
           item-border-color: #0B141A; title-color: #E9EDEF; subtitle-color: #8696A0;
           meta-color: #8696A0; badge-background-color: #21C063; badge-color: #0B141A;
           badge-position: end; }
msg_fab { position: absolute; right: 18px; bottom: 22px; width: 56px; height: 56px;
         border-radius: 16px; background-color: #21C063; icon-color: #0B141A; }

msg_chat { background-color: #0B141A; padding: 0px; }
chat_head { display: flex; flex-direction: row; align-items: center; gap: 6px;
            padding: 8px 4px 8px 4px; background-color: #1F2C34; }
chat_who { flex-grow: 1; background-color: #00000000; padding: 0px 6px; }
chat_name { color: #E9EDEF; font-size: 17px; font-weight: bold; }
chat_status { color: #8696A0; font-size: 12px; }
thread { height: 640px; background-color: #0B141A; item-background-color: #202C33;
         item-border-radius: 10px; gap: 6px; subtitle-lines: 30; subtitle-color: #E9EDEF;
         meta-color: #8696A0; }
thread:them { align-self: flex-start; max-width: 80%; }
thread:mine { align-self: flex-end; max-width: 80%; item-background-color: #005C4B;
              meta-color: #9FC2B9; }
thread:read { align-self: flex-end; max-width: 80%; item-background-color: #005C4B;
              meta-color: #53BDEB; }
thread:day { align-self: center; item-background-color: #182229; meta-color: #8696A0; }
composer { position: absolute; left: 6px; right: 6px; bottom: 6px;
           display: flex; flex-direction: row; align-items: center; gap: 6px;
           background-color: #00000000; padding: 0px; }
pill { flex-grow: 1; display: flex; flex-direction: row; align-items: center; gap: 0px;
       background-color: #202C33; border-radius: 26px; padding: 0px 4px; }
emoji, attach { width: 48px; height: 48px; background-color: #00000000; icon-color: #8696A0; }
message { flex-grow: 1; background-color: #00000000; border-width: 0px; color: #E9EDEF;
          placeholder-color: #8696A0; font-size: 16px; }
send { width: 50px; height: 50px; border-radius: 25px; background-color: #21C063;
       icon-color: #0B141A; }

/* Music */
mu_home { background-color: #121212; padding: 16px; }
mu_title, mu_section { font-size: 24px; font-weight: bold; color: #FFFFFF; margin-bottom: 8px; }
mu_section { margin-top: 18px; }
mu_filters { display: flex; flex-direction: row; justify-content: flex-start; gap: 8px; padding: 0px 0px 14px 0px;
             background-color: #121212; }
mu_chip_on { background-color: #1ED760; color: #000000; border-radius: 16px; font-size: 13px;
             text-transform: none; height: 32px; padding: 0px 14px; }
mu_chip, mu_chip2 { background-color: #2A2A2A; color: #FFFFFF; border-radius: 16px; font-size: 13px;
                    text-transform: none; height: 32px; padding: 0px 14px; }
mu_recent { background-color: #121212; item-background-color: #2A2A2A; title-color: #FFFFFF;
            subtitle-color: #B3B3B3; }
mu_mixes { background-color: #121212; title-color: #FFFFFF; subtitle-color: #B3B3B3; }
mu_player { background-color: #3B1F2B; padding: 18px; }
np_top { display: flex; flex-direction: row; align-items: center; gap: 8px;
         background-color: #00000000; padding: 0px; }
np_down, np_more { width: 48px; height: 48px; background-color: #00000000; icon-color: #FFFFFF; }
np_from { flex-grow: 1; text-align: center; color: #FFFFFF; font-size: 11px; font-weight: bold;
          letter-spacing: 1px; }
np_meta { display: flex; flex-direction: row; align-items: center; background-color: #00000000;
          padding: 0px; }
np_names { flex-grow: 1; background-color: #00000000; padding: 0px; }
np_like { width: 48px; height: 48px; background-color: #00000000; icon-color: #FFFFFF;
          active-color: #1ED760; }
np_cover { width: 100%; aspect-ratio: 1; border-radius: 8px; margin: 18px 0px 20px 0px;
           object-fit: cover; }
np_title { color: #FFFFFF; font-size: 24px; font-weight: bold; }
np_artist { color: #D6C2CA; font-size: 16px; margin-bottom: 12px; }
np_progress { accent-color: #FFFFFF; }
np_time { color: #D6C2CA; font-size: 12px; }
np_deck { display: flex; flex-direction: row; align-items: center; justify-content: space-between;
          background-color: #00000000; padding: 8px 0px; }
np_shuffle, np_prev, np_next, np_repeat { width: 52px; height: 52px; background-color: #00000000;
                                          icon-color: #FFFFFF; }
np_shuffle, np_repeat { active-color: #1ED760; }
mu_mini { background-color: #3B1F2B; color: #FFFFFF; subtitle-color: #D6C2CA; }
np_play { width: 68px; height: 68px; border-radius: 34px; background-color: #FFFFFF;
          icon-color: #000000; }

/* Photos */
ph_feed { background-color: #FFFFFF; padding: 0px; }
ph_bar { display: flex; flex-direction: row; align-items: center; padding: 10px 6px 4px 14px;
         background-color: #FFFFFF; }
ph_brand { font-size: 26px; font-weight: bold; color: #000000; }
ph_spacer, ph_spacer2 { flex-grow: 1; background-color: #00000000; padding: 0px; }
ph_heart, ph_dm, ph_post_more, ph_like, ph_comment, ph_share, ph_save {
    width: 48px; height: 48px; background-color: #00000000; icon-color: #000000; }
ph_liked { width: 48px; height: 48px; background-color: #00000000; icon-color: #FF3040; }
ph_tray { display: flex; flex-direction: row; gap: 12px; padding: 8px 12px;
          background-color: #FFFFFF; }
ph_story_cell { display: flex; flex-direction: column; align-items: center; gap: 4px;
                background-color: #FFFFFF; padding: 0px; }
ph_ring { border-color: #DD2A7B; border-width: 3px; border-radius: 31px; }
ph_story_name { font-size: 11px; color: #262626; }
ph_post_head { display: flex; flex-direction: row; align-items: center; gap: 10px;
               padding: 10px 6px 8px 12px; background-color: #FFFFFF; }
ph_post_face { border-radius: 17px; }
ph_post_names { flex-grow: 1; display: flex; flex-direction: column; align-items: flex-start; gap: 0px;
                background-color: #00000000; padding: 0px; }
ph_post_user { font-size: 14px; font-weight: bold; color: #000000; }
ph_post_place { font-size: 12px; color: #262626; }
ph_post_pic { width: 100%; object-fit: cover; }
ph_actions { display: flex; flex-direction: row; align-items: center; gap: 0px; padding: 2px 4px;
             background-color: #FFFFFF; }
ph_like_count { font-size: 14px; font-weight: bold; color: #000000; margin-left: 14px; }
ph_cap { display: flex; flex-direction: row; justify-content: flex-start; gap: 6px; padding: 2px 14px 0px 14px;
         background-color: #FFFFFF; }
ph_cap_user { font-size: 14px; font-weight: bold; color: #000000; }
ph_cap_text { font-size: 14px; color: #262626; }
ph_comments { font-size: 14px; color: #737373; margin: 4px 14px 0px 14px; }
ph_when { font-size: 11px; color: #737373; margin: 4px 14px 16px 14px; }
ph_posts { background-color: #FFFFFF; margin-bottom: 56px; }
ph_posts_row { background-color: #FFFFFF; padding: 0px 0px 8px 0px; gap: 0px; }
ph_spacer3 { flex-grow: 1; background-color: #00000000; padding: 0px; }
ph_like { active-color: #FF3040; }
ph_sponsored { font-size: 12px; color: #262626; }
ph_nav { position: absolute; left: 0px; right: 0px; bottom: 0px; display: flex; flex-direction: row;
         justify-content: space-around; background-color: #FFFFFF; padding: 4px 0px; }
ph_nav_home, ph_nav_search, ph_nav_add, ph_nav_videos, ph_nav_me {
    width: 48px; height: 48px; background-color: #00000000; icon-color: #000000; }

ph_story { background-color: #000000; padding: 0px; }
st_stage { position: relative; width: 100%; height: 100%; background-color: #000000; padding: 0px; }
st_img { width: 100%; height: 100%; object-fit: cover; }
st_bars { position: absolute; left: 8px; right: 8px; top: 8px; display: flex; flex-direction: row;
          gap: 4px; background-color: #00000000; padding: 0px; }
st_seg_on, st_seg_on2 { flex-grow: 1; height: 3px; background-color: #FFFFFF; border-radius: 2px;
                        padding: 0px; }
st_seg_off, st_seg_off2 { flex-grow: 1; height: 3px; background-color: #66FFFFFF; border-radius: 2px;
                          padding: 0px; }
st_who { position: absolute; left: 12px; top: 22px; display: flex; flex-direction: row;
         align-items: center; gap: 8px; background-color: #00000000; padding: 0px; }
st_face { border-radius: 16px; }
st_name { color: #FFFFFF; font-size: 14px; font-weight: bold; }
st_close { position: absolute; right: 8px; top: 18px; width: 48px; height: 48px;
           background-color: #00000000; icon-color: #FFFFFF; }
st_hint { position: absolute; left: 0px; right: 0px; bottom: 30px; color: #FFFFFF;
          font-size: 13px; text-align: center; }

ph_camera { background-color: #000000; padding: 0px; }
cam_stage { position: relative; width: 100%; height: 100%; background-color: #000000; padding: 0px; }
visor { width: 100%; height: 100%; }
cam_close { position: absolute; left: 10px; top: 14px; width: 48px; height: 48px;
            background-color: #00000000; icon-color: #FFFFFF; }
shutter { position: absolute; bottom: 44px; left: 150px; width: 78px; height: 78px;
          background-color: #00000000; border-color: #FFFFFF; border-width: 5px; border-radius: 39px; }
flip { position: absolute; bottom: 58px; right: 36px; width: 50px; height: 50px; border-radius: 25px;
       background-color: #55000000; icon-color: #FFFFFF; }

/* Ride */
ride { background-color: #FFFFFF; padding: 0px; }
ride_area { position: relative; width: 100%; height: 100%; padding: 0px; }
ride_map { width: 100%; height: 100%; }
ride_sheet { position: absolute; left: 0px; right: 0px; bottom: 0px; background-color: #FFFFFF;
             border-radius: 22px 22px 0px 0px; padding: 10px 16px 18px 16px; box-shadow: 12px; }
ride_handle { width: 44px; height: 5px; border-radius: 3px; background-color: #D4D4D4;
              margin-bottom: 8px; padding: 0px; }
ride_title { font-size: 20px; font-weight: bold; color: #000000; margin-bottom: 4px; }
ride_opt { background-color: #FFFFFF; title-color: #000000; subtitle-color: #5E5E5E;
           trailing-color: #000000; icon-color: #000000; }
ride_go { background-color: #000000; color: #FFFFFF; border-radius: 8px; height: 52px; margin-top: 8px;
           font-size: 16px; text-transform: none; }
"""

run(start_screen=home, theme=Theme(mode="light"))
