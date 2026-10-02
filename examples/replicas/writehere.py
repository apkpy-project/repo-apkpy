"""Four apps you know, rebuilt with ApkPy.

A chat list and a conversation you can type into, a music app's home and a
player that really plays, a photo feed -- every post a row built from
components, with a heart that turns red -- its stories and camera, a profile
whose Posts / Reels / Tagged tabs swipe over a photo grid, the settings under
its menu (a private-account switch that remembers), an edit screen whose Done
writes back into the profile, notifications with a Follow button, an explore
grid, a ride sheet over a map, a mail inbox you swipe to archive or delete
(with Undo) and a task list you hold to reorder. Every name, picture and
sound in them is made up.

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
ph_profile = Screen(id="ph_profile", scroll=True)
ph_settings = Screen(id="ph_settings", scroll=True)
ph_edit = Screen(id="ph_edit", scroll=True)
ph_activity = Screen(id="ph_activity", scroll=True)
ph_explore = Screen(id="ph_explore", scroll=True)
mail_inbox = Screen(id="mail_inbox", scroll=True)
mail_read = Screen(id="mail_read", scroll=True)
tasks = Screen(id="tasks", scroll=True)

# ── Home ────────────────────────────────────────────────────────────────────
label("Replicas", id="home_title", screen=home)
label("Apps you know, rebuilt with ApkPy.", id="home_copy", screen=home)
button("Chat", id="go_chat", icon="chat", screen=home,
       command=lambda: on_click_navigate(msg_list))
button("Music", id="go_music", icon="library_music", screen=home,
       command=lambda: on_click_navigate(mu_home))
button("Photos", id="go_photos", icon="photo_camera", screen=home,
       command=lambda: on_click_navigate(ph_feed))
button("Ride", id="go_ride", icon="directions_car", screen=home,
       command=lambda: on_click_navigate(ride))
button("Mail", id="go_mail", icon="mail", screen=home,
       command=lambda: on_click_navigate(mail_inbox))
button("Tasks", id="go_tasks", icon="task_alt", screen=home,
       command=lambda: on_click_navigate(tasks))


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

CHATS = [
    {"name": "Mara Vale", "last": "Yes! 8pm at Barr", "time": "21:42", "unread": "2", "group": ""},
    {"name": "Liv Moreau", "last": "Photo", "time": "20:15", "unread": "", "group": ""},
    {"name": "Family", "last": "Mum: Dinner on Sunday?", "time": "19:03", "unread": "5", "group": "yes"},
    {"name": "Theo Park", "last": "Sent you the tickets", "time": "Yesterday", "unread": "", "group": ""},
    {"name": "Running club", "last": "Ana: 7am at the park", "time": "Yesterday", "unread": "", "group": "yes"},
    {"name": "Nell Shore", "last": "Thank you!!", "time": "Monday", "unread": "", "group": ""},
]


def chat_filter(kind):
    shown = []
    for chat in CHATS:
        if kind == "Unread" and chat["unread"] == "":
            continue
        if kind == "Groups" and chat["group"] != "yes":
            continue
        shown.append(chat)
    chats.set_items(shown)


# WhatsApp's filters: one at a time, no check mark, and always one on --
# tapping the selected filter again leaves it selected.
chips(["All", "Unread", "Groups"], selected="All", check=False, required=True,
      on_change=chat_filter, id="msg_chips", screen=msg_list)


def open_chat(item):
    chat_name.set_value(item["name"])
    on_click_navigate(msg_chat)


chats = virtual_collection(
    CHATS,
    template={"avatar": "{name}", "title": "{name}", "subtitle": "{last}",
              "meta": "{time}", "badge": "{unread}"},
    id="msg_chats", item_height="auto", on_click=open_chat, screen=msg_list,
)
button("", id="msg_fab", icon="add_comment", describe="New chat", screen=msg_list,
       command=lambda: toast("New chat"))

# ── Chat: a conversation ─────────────────────────────────────────────────
head = container(id="chat_head", screen=msg_chat)
button("", id="chat_back", icon="arrow_back", describe="Back", parent=head, command=back)
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


def music_filter(kind):
    if kind == "Podcasts":
        mu_made.set_value("Podcasts for you")
    elif kind == "Music":
        mu_made.set_value("Music for you")
    else:
        mu_made.set_value("Made for you")


label("Good evening", id="mu_title", screen=mu_home)
# Spotify's chips: one at a time, green when on, no check mark, always one on.
chips(["All", "Music", "Podcasts"], selected="All", check=False, required=True,
      on_change=music_filter, id="mu_filters", screen=mu_home)
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
mu_made = label("Made for you", id="mu_section", screen=mu_home)
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
button("", id="ph_heart", icon="favorite_border", describe="Notifications", parent=bar,
       command=lambda: on_click_navigate(ph_activity))
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
       command=lambda: on_click_navigate(ph_explore))
button("", id="ph_nav_add", icon="add_box", describe="New post", parent=nav,
       command=lambda: on_click_navigate(ph_camera))
button("", id="ph_nav_videos", icon="slideshow", describe="Videos", parent=nav,
       command=lambda: toast("Videos"))
button("", id="ph_nav_me", icon="account_circle", describe="Profile", parent=nav,
       command=lambda: on_click_navigate(ph_profile))

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
        back()


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
button("", id="st_close", icon="close", describe="Close", parent=stage, command=back)
label("Tap to see the next story", id="st_hint", parent=stage)

# ── Photos: the camera ──────────────────────────────────────────────────────────────


def shot(ok, path):
    if ok:
        toast("Photo saved")
    else:
        toast("No photo")


cam_stage = container(id="cam_stage", screen=ph_camera)
visor = camera_view(id="visor", parent=cam_stage, lens="back", fit="cover", on_capture=shot)
button("", id="cam_close", icon="close", describe="Close", parent=cam_stage, command=back)
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

# ── Photos: a profile ─────────────────────────────────────────────────────────
pf_top = container(id="pf_top", screen=ph_profile)
button("", id="pf_back", icon="arrow_back", describe="Back", parent=pf_top, command=back)
pf_handle = label("mara.vale", id="pf_handle", parent=pf_top)
container(id="pf_spacer", parent=pf_top)
button("", id="pf_menu", icon="menu", describe="Settings", parent=pf_top,
       command=lambda: on_click_navigate(ph_settings))

pf_head = container(id="pf_head", screen=ph_profile)
avatar("face2.png", size=86, id="pf_face", parent=pf_head, describe="mara.vale")
pf_stats = container(id="pf_stats", parent=pf_head)
for number, word in [("48", "posts"), ("1,284", "followers"), ("312", "following")]:
    pf_cell = container(id="pf_stat", parent=pf_stats)
    label(number, id="pf_stat_n", parent=pf_cell)
    label(word, id="pf_stat_l", parent=pf_cell)
pf_name = label("Mara Vale", id="pf_name", screen=ph_profile)
pf_bio = label("Photographer in Lisbon. Last light, every day.", id="pf_bio", screen=ph_profile)
pf_actions = container(id="pf_actions", screen=ph_profile)
button("Edit profile", id="pf_edit", parent=pf_actions, command=lambda: on_click_navigate(ph_edit))
button("Share profile", id="pf_share", parent=pf_actions, command=lambda: toast("Share profile"))

PHOTOS = [
    {"id": "g0", "picture": "post1.jpg"},
    {"id": "g1", "picture": "post2.jpg"},
    {"id": "g2", "picture": "story1.jpg"},
    {"id": "g3", "picture": "story2.jpg"},
    {"id": "g4", "picture": "story3.jpg"},
    {"id": "g5", "picture": "cover1.png"},
    {"id": "g6", "picture": "cover2.png"},
    {"id": "g7", "picture": "cover3.png"},
    {"id": "g8", "picture": "cover4.png"},
    {"id": "g9", "picture": "cover5.png"},
    {"id": "g10", "picture": "cover6.png"},
    {"id": "g11", "picture": "post1.jpg"},
]


def open_photo(item):
    toast("Photo " + item["id"])


def tile(row):
    image("{picture}", id="pf_tile", parent=row, aspect_ratio="1:1", describe="",
          command=lambda item: open_photo(item))


pf_tabs = pager(id="pf_tabs", screen=ph_profile)
pf_posts = tab(icon="grid_on", describe="Posts", id="pf_posts", parent=pf_tabs)
pf_reels = tab(icon="slideshow", describe="Reels", id="pf_reels", parent=pf_tabs)
pf_tagged = tab(icon="person_pin", describe="Tagged", id="pf_tagged", parent=pf_tabs)

pf_grid = virtual_collection(PHOTOS, row=tile, layout="grid", columns=3,
                             id="pf_grid", parent=pf_posts)

REELS = [
    {"id": "r0", "picture": "story1.jpg", "views": "12.4K"},
    {"id": "r1", "picture": "story2.jpg", "views": "8,210"},
    {"id": "r2", "picture": "story3.jpg", "views": "3,902"},
]


def reel(row):
    image("{picture}", id="pf_reel", parent=row, aspect_ratio="9:16", describe="")
    label("{views}", id="pf_reel_views", parent=row)


pf_reel_grid = virtual_collection(REELS, row=reel, layout="grid", columns=3,
                                  id="pf_reel_grid", parent=pf_reels)
label("Photos of you", id="pf_tag_title", parent=pf_tagged)
label("When people tag you in photos, they'll appear here.", id="pf_tag_copy",
      parent=pf_tagged)


# One header for the screens under the profile: a function that builds UI is
# written out again at each call. back() closes the screen, so the one under
# it comes back as it was -- on_click_navigate() would open a new copy.
def ph_header(title, screen):
    head = container(id="ph_head", screen=screen)
    button("", id="ph_head_back", icon="arrow_back", describe="Back", parent=head,
           command=back)
    label(title, id="ph_head_title", parent=head)
    return head


# ── Photos: settings ────────────────────────────────────────────────────────
def private_account(value):
    storage.set("private", value)
    if value == "true":
        toast("Only your followers see your posts now")
    else:
        toast("Anyone can see your posts now")


def log_out():
    toast("Logged out of mara.vale")
    on_click_navigate(home)


log_out_dialog = modal(
    "Log out of mara.vale?",
    content="You can log back in any time with your password.",
    confirm_text="Log out",
    cancel_text="Cancel",
    on_confirm=log_out,
    id="set_logout_dialog",
)

ph_header("Settings and activity", ph_settings)
inputs("Search", id="set_search", screen=ph_settings)

label("Your account", id="set_section", screen=ph_settings)
set_account = container(id="set_group", screen=ph_settings)
list_row("Account", subtitle="Password, security, personal details", icon="account_circle",
         trailing_icon="chevron_right", id="set_row", parent=set_account,
         command=lambda: toast("Account"))

label("How you use the app", id="set_section", screen=ph_settings)
set_use = container(id="set_group", screen=ph_settings)
list_row("Saved", icon="bookmark_border", trailing_icon="chevron_right", id="set_row",
         parent=set_use, command=lambda: toast("Saved"))
list_row("Archive", icon="history", trailing_icon="chevron_right", id="set_row",
         parent=set_use, command=lambda: toast("Archive"))
list_row("Your activity", icon="timeline", trailing_icon="chevron_right", id="set_row",
         parent=set_use, command=lambda: toast("Your activity"))
list_row("Notifications", icon="notifications_none", trailing_icon="chevron_right",
         id="set_row", parent=set_use, command=lambda: on_click_navigate(ph_activity))
list_row("Time management", subtitle="42 min a day this week", icon="schedule",
         trailing_icon="chevron_right", id="set_row", parent=set_use,
         command=lambda: toast("Time management"))

label("Who can see your content", id="set_section", screen=ph_settings)
set_privacy = container(id="set_group", screen=ph_settings)
set_private = inputs("Private account", type="switch", id="set_private", parent=set_privacy,
                     on_change=private_account)
set_private.set_value(storage.get("private"))
set_people = container(id="set_group", screen=ph_settings)
list_row("Close friends", icon="star_border", trailing="12", trailing_icon="chevron_right",
         id="set_row", parent=set_people, command=lambda: toast("Close friends"))
list_row("Blocked", icon="block", trailing="3", trailing_icon="chevron_right",
         id="set_row", parent=set_people, command=lambda: toast("Blocked"))
list_row("Hide story and live", icon="visibility_off", trailing_icon="chevron_right",
         id="set_row", parent=set_people, command=lambda: toast("Hide story and live"))

label("Your app and media", id="set_section", screen=ph_settings)
set_app = container(id="set_group", screen=ph_settings)
list_row("Language", icon="language", trailing="English", trailing_icon="chevron_right",
         id="set_row", parent=set_app, command=lambda: toast("Language"))
list_row("Accessibility", icon="accessibility", trailing_icon="chevron_right",
         id="set_row", parent=set_app, command=lambda: toast("Accessibility"))
list_row("Data usage and media quality", icon="signal_cellular_alt",
         trailing_icon="chevron_right", id="set_row", parent=set_app,
         command=lambda: toast("Data usage"))

label("Login", id="set_section", screen=ph_settings)
button("Add account", id="set_add", screen=ph_settings, command=lambda: toast("Add account"))
button("Log out", id="set_logout", screen=ph_settings, command=lambda: log_out_dialog.open())


# ── Photos: edit profile ────────────────────────────────────────────────────
# Done writes the three fields back into the profile, on another screen.
def save_profile():
    name = ed_name.get_value()
    handle = ed_user.get_value()
    bio = ed_bio.get_value()
    pf_name.set_value(name)
    pf_handle.set_value(handle)
    pf_bio.set_value(bio)
    toast("Profile saved")
    back()


ed_bar = ph_header("Edit profile", ph_edit)
button("", id="ed_done", icon="check", describe="Save", parent=ed_bar, command=save_profile)
ed_face_box = container(id="ed_face_box", screen=ph_edit)
avatar("face2.png", size=86, id="ed_face", parent=ed_face_box, describe="mara.vale")
button("Edit picture or avatar", id="ed_picture", parent=ed_face_box,
       command=lambda: toast("Choose a photo"))
label("Name", id="ed_label", screen=ph_edit)
ed_name = inputs("Name", id="ed_field", screen=ph_edit)
ed_name.set_value("Mara Vale")
label("Username", id="ed_label", screen=ph_edit)
ed_user = inputs("Username", id="ed_field", screen=ph_edit)
ed_user.set_value("mara.vale")
label("Pronouns", id="ed_label", screen=ph_edit)
inputs("Pronouns", id="ed_field", screen=ph_edit)
label("Bio", id="ed_label", screen=ph_edit)
ed_bio = inputs("Bio", id="ed_field", screen=ph_edit)
ed_bio.set_value("Photographer in Lisbon. Last light, every day.")
ed_more = container(id="ed_more", screen=ph_edit)
list_row("Add link", icon="link", trailing_icon="chevron_right", id="set_row",
         parent=ed_more, command=lambda: toast("Add link"))
list_row("Gender", icon="person", trailing="Prefer not to say", trailing_icon="chevron_right",
         id="set_row", parent=ed_more, command=lambda: toast("Gender"))
button("Switch to professional account", id="ed_blue", screen=ph_edit,
       command=lambda: toast("Professional account"))
button("Personal information settings", id="ed_blue", screen=ph_edit,
       command=lambda: toast("Personal information"))


# ── Photos: notifications ───────────────────────────────────────────────────
TODAY = [
    {"id": "n1", "face": "face3.png", "user": "liv.moreau", "what": "liked your photo.",
     "when": "2h", "picture": "post1.jpg", "follow": "", "following": ""},
    {"id": "n2", "face": "face4.png", "user": "theo.park", "what": "commented: Those colours!",
     "when": "4h", "picture": "post2.jpg", "follow": "", "following": ""},
    {"id": "n3", "face": "face5.png", "user": "nell.shore", "what": "liked your story.",
     "when": "6h", "picture": "story1.jpg", "follow": "", "following": ""},
]
WEEK = [
    {"id": "w1", "face": "face1.png", "user": "sam.okafor", "what": "started following you.",
     "when": "2d", "picture": "", "follow": "yes", "following": ""},
    {"id": "w2", "face": "face3.png", "user": "liv.moreau",
     "what": "mentioned you: @mara.vale next week?", "when": "3d", "picture": "story3.jpg",
     "follow": "", "following": ""},
    {"id": "w3", "face": "face4.png", "user": "ana.rocha", "what": "started following you.",
     "when": "5d", "picture": "", "follow": "", "following": "yes"},
]


def follow(item):
    # Two buttons, one shown at a time: update_item swaps them on this row.
    if item["following"] == "yes":
        week.update_item(item["id"], {"follow": "yes", "following": ""})
    else:
        week.update_item(item["id"], {"follow": "", "following": "yes"})


def note_row(row):
    avatar("{face}", size=44, id="ac_face", parent=row, describe="{user}")
    words = container(id="ac_words", parent=row)
    label("{user}", id="ac_user", parent=words)
    label("{what}", id="ac_what", parent=words)
    label("{when}", id="ac_when", parent=words)
    image("{picture}", id="ac_pic", parent=row, aspect_ratio="1:1", describe="",
          visible="{picture}")
    button("Follow", id="ac_follow", parent=row, visible="{follow}",
           command=lambda item: follow(item))
    button("Following", id="ac_following", parent=row, visible="{following}",
           command=lambda item: follow(item))


ph_header("Notifications", ph_activity)
label("Today", id="ac_section", screen=ph_activity)
today = virtual_collection(TODAY, row=note_row, id="ac_today", screen=ph_activity)
label("This week", id="ac_section", screen=ph_activity)
week = virtual_collection(WEEK, row=note_row, id="ac_week", screen=ph_activity)


# ── Photos: explore ─────────────────────────────────────────────────────────
EXPLORE = [
    {"id": "e0", "picture": "story2.jpg"}, {"id": "e1", "picture": "cover3.png"},
    {"id": "e2", "picture": "post2.jpg"}, {"id": "e3", "picture": "cover5.png"},
    {"id": "e4", "picture": "story1.jpg"}, {"id": "e5", "picture": "cover1.png"},
    {"id": "e6", "picture": "post1.jpg"}, {"id": "e7", "picture": "cover6.png"},
    {"id": "e8", "picture": "story3.jpg"}, {"id": "e9", "picture": "cover2.png"},
    {"id": "e10", "picture": "cover4.png"}, {"id": "e11", "picture": "story2.jpg"},
    {"id": "e12", "picture": "post1.jpg"}, {"id": "e13", "picture": "cover3.png"},
    {"id": "e14", "picture": "story1.jpg"},
]


def explore_tile(row):
    image("{picture}", id="ex_tile", parent=row, aspect_ratio="1:1", describe="",
          command=lambda item: open_photo(item))


ex_bar = container(id="ex_bar", screen=ph_explore)
button("", id="ph_head_back", icon="arrow_back", describe="Back", parent=ex_bar, command=back)
inputs("Search", id="ex_search", parent=ex_bar)
virtual_collection(EXPLORE, row=explore_tile, layout="grid", columns=3,
                   id="ex_grid", screen=ph_explore)


# ── Mail: an inbox you swipe ────────────────────────────────────────────────
# Swipe right to archive, left to delete: each leaves the list at once, a
# snackbar offers Undo, and the app only hears about it once the chance has
# passed. TalkBack offers Archive and Delete on every row -- no gesture needed.
MAIL = [
    {"id": "e1", "face": "face3.png", "sender": "Liv Moreau", "subject": "Saturday at the market?",
     "preview": "I'll bring the good coffee if you bring the bread", "when": "9:41",
     "unread": "yes", "read": "", "starred": ""},
    {"id": "e2", "face": "face4.png", "sender": "Northline Travel", "subject": "Your trip to Porto is confirmed",
     "preview": "Booking NL-2931 -- Thursday, 08:12 from Lisbon Oriente", "when": "8:05",
     "unread": "yes", "read": "", "starred": "yes"},
    {"id": "e3", "face": "face2.png", "sender": "Mara Vale", "subject": "Photos from the river",
     "preview": "Twelve of them, the light was unreal after seven", "when": "Yesterday",
     "unread": "", "read": "yes", "starred": "yes"},
    {"id": "e4", "face": "face5.png", "sender": "Nell Shore", "subject": "Late train home",
     "preview": "Missed the 23:10 again. Next week we leave earlier", "when": "Mon",
     "unread": "", "read": "yes", "starred": ""},
    {"id": "e5", "face": "face1.png", "sender": "Theo Park", "subject": "Band practice moved",
     "preview": "Same room, Wednesday instead of Tuesday", "when": "Sun",
     "unread": "", "read": "yes", "starred": ""},
]


GONE = []


def archive_mail(item):
    GONE.append(item["id"])
    toast(item["sender"] + " archived")


def delete_mail(item):
    GONE.append(item["id"])
    toast(item["sender"] + " deleted")


def filter_mail(kind):
    shown = []
    for mail in MAIL:
        if mail["id"] in GONE:
            continue
        if kind == "Unread" and mail["unread"] != "yes":
            continue
        if kind == "Starred" and mail["starred"] != "yes":
            continue
        shown.append(mail)
    mail_list.set_items(shown)


def open_mail(item):
    mr_subject.set_value(item["subject"])
    mr_sender.set_value(item["sender"])
    mr_body.set_value(item["preview"] + ".")
    on_click_navigate(mail_read)


def mail_row(row):
    avatar("{face}", size=40, id="ml_face", parent=row, describe="{sender}")
    words = container(id="ml_words", parent=row)
    label("{sender}", id="ml_sender_new", parent=words, visible="{unread}")
    label("{sender}", id="ml_sender", parent=words, visible="{read}")
    label("{subject}", id="ml_subject_new", parent=words, visible="{unread}")
    label("{subject}", id="ml_subject", parent=words, visible="{read}")
    label("{preview}", id="ml_preview", parent=words)
    label("{when}", id="ml_when", parent=row)


mail_bar = container(id="ml_bar", screen=mail_inbox)
button("", id="ml_back", icon="arrow_back", describe="Back", parent=mail_bar, command=back)
inputs("Search in mail", id="ml_search", parent=mail_bar)
chips(["All", "Unread", "Starred"], selected="All", required=True,
      on_change=filter_mail, id="ml_filters", screen=mail_inbox)
label("Inbox", id="ml_title", screen=mail_inbox)
mail_list = virtual_collection(
    MAIL, row=mail_row, id="ml_list", screen=mail_inbox, on_click=open_mail,
    swipe_right=swipe("archive", "Archive", on_swipe=archive_mail, color="#1E7A46",
                      undo="Conversation archived"),
    swipe_left=swipe("delete", "Delete", on_swipe=delete_mail, undo="Conversation deleted"),
)
label("Swipe a message to archive or delete it.", id="ml_hint", screen=mail_inbox)

mr_bar = container(id="mr_bar", screen=mail_read)
button("", id="mr_back", icon="arrow_back", describe="Back", parent=mr_bar, command=back)
container(id="mr_spacer", parent=mr_bar)
button("", id="mr_archive", icon="archive", describe="Archive", parent=mr_bar,
       command=lambda: toast("Archived"))
button("", id="mr_delete", icon="delete", describe="Delete", parent=mr_bar,
       command=lambda: toast("Deleted"))
mr_subject = label("", id="mr_subject", screen=mail_read)
mr_sender = label("", id="mr_sender", screen=mail_read)
mr_body = label("", id="mr_body", screen=mail_read)
button("Reply", id="mr_reply", icon="reply", screen=mail_read, command=lambda: toast("Reply"))


# ── Tasks: a list you reorder ───────────────────────────────────────────────
# Hold a task to lift it and drop it somewhere else; swipe right to finish it,
# left to push it to tomorrow -- that one keeps its row and changes its date.
# TalkBack offers Done, Tomorrow, Move up and Move down on every task.
TASKS = [
    {"id": "t1", "title": "Book the Porto train", "when": "Today"},
    {"id": "t2", "title": "Send Liv the market list", "when": "Today"},
    {"id": "t3", "title": "Pick up the prints", "when": "Tomorrow"},
    {"id": "t4", "title": "Renew the gym card", "when": "Friday"},
    {"id": "t5", "title": "Call the landlord about the boiler", "when": "Next week"},
]


def task_done(item):
    toast("Done: " + item["title"])


def task_tomorrow(item):
    task_list.update_item(item["id"], {"when": "Tomorrow"})
    toast(item["title"] + " -- tomorrow")


def task_moved(item, index):
    toast(item["title"] + " is number " + str(index + 1))


def task_row(row):
    button("", id="tk_check", icon="radio_button_unchecked", describe="", parent=row)
    words = container(id="tk_words", parent=row)
    label("{title}", id="tk_title", parent=words)
    label("{when}", id="tk_when", parent=words)
    button("", id="tk_handle", icon="drag_indicator", describe="", parent=row)


tk_bar = container(id="tk_bar", screen=tasks)
button("", id="tk_back", icon="arrow_back", describe="Back", parent=tk_bar, command=back)
label("My tasks", id="tk_heading", parent=tk_bar)
label("Hold a task to move it. Swipe it to finish it, or to leave it for tomorrow.",
      id="tk_hint", screen=tasks)
task_list = virtual_collection(
    TASKS, row=task_row, id="tk_list", screen=tasks, on_reorder=task_moved,
    swipe_right=swipe("check_circle", "Done", on_swipe=task_done, color="#1E7A46"),
    swipe_left=swipe("event", "Tomorrow", on_swipe=task_tomorrow, keep=True),
)

style = """
home { background-color: #FFFFFF; padding: 20px; }
home_title { font-size: 30px; font-weight: bold; color: #111111; }
home_copy { font-size: 15px; color: #555555; margin-bottom: 14px; }
go_chat, go_music, go_photos, go_ride, go_mail, go_tasks { height: 56px; border-radius: 16px; margin-bottom: 10px;
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
msg_chips { margin: 2px 14px 0px 14px; background-color: #202C33; color: #8696A0;
            border-color: transparent; indicator-color: #103529; active-color: #D9FDD3;
            border-radius: 16px; font-size: 13px; }
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
mu_filters { background-color: #2A2A2A; color: #FFFFFF; border-color: transparent;
             indicator-color: #1ED760; active-color: #000000; border-radius: 16px;
             font-size: 13px; margin-bottom: 6px; }
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
ph_profile { background-color: #FFFFFF; padding: 0px; }
pf_top { display: flex; flex-direction: row; align-items: center; padding: 6px 6px 0px 4px;
         background-color: #FFFFFF; }
pf_back, pf_menu { width: 48px; height: 48px; background-color: #00000000; icon-color: #000000; }
pf_handle { font-size: 20px; font-weight: bold; color: #000000; }
pf_spacer { flex-grow: 1; background-color: #00000000; padding: 0px; }
pf_head { display: flex; flex-direction: row; align-items: center; gap: 18px;
          padding: 8px 16px; background-color: #FFFFFF; }
pf_stats { flex-grow: 1; display: flex; flex-direction: row; justify-content: space-around;
           background-color: #FFFFFF; padding: 0px; }
pf_stat { display: flex; flex-direction: column; align-items: center; gap: 0px;
          background-color: #FFFFFF; padding: 0px; }
pf_stat_n { font-size: 17px; font-weight: bold; color: #000000; }
pf_stat_l { font-size: 13px; color: #262626; }
pf_name { font-size: 14px; font-weight: bold; color: #000000; margin: 4px 16px 0px 16px; }
pf_bio { font-size: 14px; color: #262626; margin: 2px 16px 10px 16px; }
pf_actions { display: flex; flex-direction: row; gap: 6px; padding: 0px 16px 12px 16px;
             background-color: #FFFFFF; }
pf_edit, pf_share { flex-grow: 1; height: 34px; border-radius: 8px; background-color: #EFEFEF;
                    color: #000000; font-size: 14px; font-weight: bold; text-transform: none; }
pf_grid { background-color: #FFFFFF; height: auto; }
pf_tabs { active-color: #000000; color: #8E8E8E; indicator-color: #000000;
          border-color: #DBDBDB; background-color: #FFFFFF; }
pf_posts, pf_reels, pf_tagged { background-color: #FFFFFF; padding: 0px; }
pf_reel_grid { background-color: #FFFFFF; height: auto; }
pf_reel_grid_row { padding: 1px; background-color: #FFFFFF; }
pf_reel { width: 100%; object-fit: cover; }
pf_reel_views { font-size: 12px; font-weight: bold; color: #262626; margin-left: 4px; }
pf_tagged { padding: 40px 32px; }
pf_tag_title { font-size: 22px; font-weight: bold; color: #000000; text-align: center; }
pf_tag_copy { font-size: 14px; color: #737373; text-align: center; margin-top: 8px; }
pf_grid_row { padding: 1px; background-color: #FFFFFF; }
pf_tile { width: 100%; object-fit: cover; }

/* Photos: settings, edit profile, notifications, explore. The blue and the
   red are a shade darker than the app they copy, for 4.5:1 on white. Its
   buttons are sentence case with no tracking: letter-spacing: 0 replaces the
   0.089em Material spaces ALL-CAPS labels with. */
pf_edit, pf_share, ed_picture, ed_blue, set_add, set_logout, ac_follow, ac_following {
    letter-spacing: 0px; }
ph_settings, ph_edit, ph_activity, ph_explore {
    background-color: #FFFFFF; padding: 0px 0px 24px 0px; gap: 0px; }
ph_head { display: flex; flex-direction: row; align-items: center; gap: 4px;
          padding: 6px 6px 2px 4px; background-color: #FFFFFF; }
ph_head_back { width: 48px; height: 48px; background-color: #00000000; icon-color: #000000; }
ph_head_title { flex-grow: 1; font-size: 20px; font-weight: bold; color: #000000; }
set_search, ex_search { background-color: #EFEFEF; border-width: 0px; border-radius: 10px;
                        height: 40px; color: #000000; placeholder-color: #6E6E6E; font-size: 15px; }
set_search { margin: 6px 16px 4px 16px; }
set_section { font-size: 14px; font-weight: bold; color: #737373; margin: 18px 16px 2px 16px; }
set_group { background-color: #FFFFFF; padding: 0px; }
set_row { background-color: #FFFFFF; title-color: #000000; subtitle-color: #737373;
          trailing-color: #737373; icon-color: #000000; }
set_private { color: #000000; accent-color: #0074E0; font-size: 16px; margin: 0px 16px; }
set_add, set_logout { background-color: #00000000; font-size: 16px; text-transform: none;
                      margin: 0px 4px; }
set_add { color: #0074E0; }
set_logout { color: #D93446; }

ed_done { width: 48px; height: 48px; background-color: #00000000; icon-color: #0074E0; }
ed_face_box { display: flex; flex-direction: column; align-items: center; gap: 4px;
              padding: 12px 0px 8px 0px; background-color: #FFFFFF; }
ed_face { border-radius: 43px; }
ed_picture { background-color: #00000000; color: #0074E0; font-size: 14px; font-weight: bold;
             text-transform: none; }
ed_label { font-size: 12px; color: #737373; margin: 12px 16px 0px 16px; }
ed_field { background-color: #FFFFFF; border-color: #DBDBDB; border-width: 1px; border-radius: 10px;
           color: #000000; placeholder-color: #6E6E6E; font-size: 15px; margin: 4px 16px 0px 16px; }
ed_more { background-color: #FFFFFF; padding: 0px; margin-top: 14px; }
ed_blue { background-color: #00000000; color: #0074E0; font-size: 15px; text-transform: none;
          margin: 0px 4px; }

ac_section { font-size: 16px; font-weight: bold; color: #000000; margin: 12px 16px 4px 16px; }
ac_today, ac_week { background-color: #FFFFFF; height: auto; }
ac_today_row, ac_week_row { display: flex; flex-direction: row; align-items: center; gap: 12px;
                            padding: 8px 16px; background-color: #FFFFFF; }
ac_face { border-radius: 22px; }
ac_words { flex-grow: 1; display: flex; flex-direction: column; align-items: flex-start; gap: 0px;
           background-color: #FFFFFF; padding: 0px; }
ac_user { font-size: 14px; font-weight: bold; color: #000000; }
ac_what { font-size: 14px; color: #262626; }
ac_when { font-size: 12px; color: #737373; }
ac_pic { width: 44px; height: 44px; object-fit: cover; }
ac_follow, ac_following { height: 32px; border-radius: 8px; font-size: 14px; font-weight: bold;
                          text-transform: none; padding: 0px 16px; }
ac_follow { background-color: #0074E0; color: #FFFFFF; }
ac_following { background-color: #EFEFEF; color: #000000; }

ex_bar { display: flex; flex-direction: row; align-items: center; gap: 4px;
         padding: 6px 12px 6px 4px; background-color: #FFFFFF; }
ex_search { flex-grow: 1; }
ex_grid { background-color: #FFFFFF; height: auto; }
ex_grid_row { padding: 1px; background-color: #FFFFFF; }
ex_tile { width: 100%; object-fit: cover; }

/* Mail and Tasks: swiped and reordered rows */
mail_inbox, mail_read, tasks { background-color: #FFFFFF; padding: 0px 0px 24px 0px; gap: 0px; }
ml_bar, tk_bar { display: flex; flex-direction: row; align-items: center; gap: 4px;
                 padding: 6px 12px 6px 4px; background-color: #FFFFFF; }
ml_back, mr_back, tk_back, mr_archive, mr_delete {
    width: 48px; height: 48px; background-color: #00000000; icon-color: #1F1F1F; }
ml_search { flex-grow: 1; height: 44px; border-radius: 22px; border-width: 0px;
            background-color: #EEF1F6; color: #1F1F1F; placeholder-color: #5F6368; font-size: 15px; }
ml_filters { margin: 4px 16px 0px 16px; }
ml_title { font-size: 13px; font-weight: bold; color: #5F6368; margin: 10px 16px 4px 16px; }
ml_list { background-color: #FFFFFF; height: auto; }
ml_list_row { display: flex; flex-direction: row; align-items: center; gap: 14px;
              padding: 10px 16px; background-color: #FFFFFF; }
ml_face { border-radius: 20px; }
ml_words { flex-grow: 1; display: flex; flex-direction: column; align-items: flex-start; gap: 1px;
           background-color: #FFFFFF; padding: 0px; }
ml_sender_new, ml_subject_new { font-size: 15px; font-weight: bold; color: #1F1F1F; }
ml_sender, ml_subject { font-size: 15px; color: #1F1F1F; }
ml_preview { font-size: 14px; color: #5F6368; }
ml_when { font-size: 12px; color: #5F6368; }
ml_hint { font-size: 13px; color: #5F6368; text-align: center; margin: 16px 24px 0px 24px; }
mr_bar { display: flex; flex-direction: row; align-items: center; padding: 6px 4px;
         background-color: #FFFFFF; }
mr_spacer { flex-grow: 1; background-color: #00000000; padding: 0px; }
mr_subject { font-size: 22px; color: #1F1F1F; margin: 8px 16px 0px 16px; }
mr_sender { font-size: 14px; font-weight: bold; color: #1F1F1F; margin: 16px 16px 0px 16px; }
mr_body { font-size: 15px; color: #3C4043; margin: 12px 16px 0px 16px; }
mr_reply { background-color: #00000000; color: #0B57D0; border-color: #747775; border-width: 1px;
           border-radius: 20px; height: 40px; text-transform: none; letter-spacing: 0px;
           icon-color: #0B57D0; margin: 24px 16px 0px 16px; }

tk_heading { font-size: 22px; color: #1F1F1F; }
tk_hint { font-size: 13px; color: #5F6368; margin: 0px 16px 8px 16px; }
tk_list { background-color: #FFFFFF; height: auto; }
tk_list_row { display: flex; flex-direction: row; align-items: center; gap: 4px;
              padding: 4px 8px 4px 4px; background-color: #FFFFFF; }
tk_check, tk_handle { width: 48px; height: 48px; background-color: #00000000; icon-color: #5F6368; }
tk_words { flex-grow: 1; display: flex; flex-direction: column; align-items: flex-start; gap: 0px;
           background-color: #FFFFFF; padding: 0px; }
tk_title { font-size: 16px; color: #1F1F1F; }
tk_when { font-size: 13px; color: #0B57D0; }
"""

run(start_screen=home, theme=Theme(mode="light"))
