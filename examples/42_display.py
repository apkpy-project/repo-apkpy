"""Display - kept on, brighter, without its bars, and which way up.

A recipe that keeps the phone awake while you cook, a ticket shown at full
brightness, and a player that lies down and takes the whole screen.
display.keep_on() stops the phone sleeping, display.brightness() says how
bright this screen is, display.immersive() hides the status and navigation
bars, and display.orientation() says which way up it is.

What a screen asks for is its own: it ends when the screen is closed, and
none of it needs a permission. Screen(orientation=) and run(orientation=)
say which way up a screen is before anything is asked.

In the Previewer, Ctrl+Left and Ctrl+Right turn the phone.

Needs ApkPy 1.13.0.
"""

from apkpy_lib import *

home = Screen(id="home", scroll=True)
player = Screen(id="player", orientation="landscape")

label("Display", id="title", screen=home)
label("Kept on, brighter, and which way up.", id="lead", screen=home)

cook_card = container(id="cook_card", screen=home)
label("COOK MODE", id="cook_kicker", parent=cook_card)
label("Lemon risotto", id="cook_name", parent=cook_card)
cook_note = label("The phone sleeps as usual", id="cook_note", parent=cook_card)
cook_actions = container(id="cook_actions", parent=cook_card)

ticket_card = container(id="ticket_card", screen=home)
label("TICKET", id="ticket_kicker", parent=ticket_card)
label("LIS  >  OPO", id="ticket_name", parent=ticket_card)
ticket_note = label("Gate 14, seat 21C", id="ticket_note", parent=ticket_card)
ticket_actions = container(id="ticket_actions", parent=ticket_card)

way_card = container(id="way_card", screen=home)
label("WHICH WAY UP", id="way_kicker", parent=way_card)
way_note = label("Stays upright", id="way_note", parent=way_card)
way_actions = container(id="way_actions", parent=way_card)

film_card = container(id="film_card", screen=home)
label("PLAYER", id="film_kicker", parent=film_card)
label("Night train to Porto", id="film_name", parent=film_card)
label("A screen that lies down, with nothing around it", id="film_note", parent=film_card)
film_actions = container(id="film_actions", parent=film_card)


def cook(on):
    display.keep_on(on)
    if on == "true":
        cook_note.set_value("Stays on while this screen is open")
    else:
        cook_note.set_value("The phone sleeps as usual")


def show_ticket():
    if show.get_value() == "Show at the gate":
        display.brightness(1)
        ticket_note.set_value("As bright as the phone goes")
        show.set_value("Done")
    else:
        display.brightness("auto")
        ticket_note.set_value("Gate 14, seat 21C")
        show.set_value("Show at the gate")


def turn(way):
    if way == "Upright":
        display.orientation("portrait")
        way_note.set_value("Stays upright")
    elif way == "On its side":
        display.orientation("landscape")
        way_note.set_value("Stays on its side")
    else:
        display.orientation("auto")
        way_note.set_value("Turns with the phone")


def playing():
    display.keep_on(True)
    display.immersive(True)


inputs("Keep the screen on", id="awake", type="switch", on_change=cook, parent=cook_actions)
show = button("Show at the gate", id="show", icon="qr_code_2", command=show_ticket, parent=ticket_actions)
segmented(["Upright", "On its side", "Follow"], id="way", on_change=turn, parent=way_actions)
watch = button("Watch", id="watch", icon="play_arrow", parent=film_actions)
home.on_click_navigate(button=watch, to=player)

label("NOW PLAYING", id="now_kicker", screen=player)
label("Night train to Porto", id="now_title", screen=player)
label("1 h 42 min left", id="now_time", screen=player)
player_actions = container(id="player_actions", screen=player)
button("Close", id="close", icon="close", variant="outlined", command=back, parent=player_actions)

lifecycle(player, on_mount=playing)

theme = Theme(primary="#3B5BDB")

style = """
home {
    background-color: var(--background);
    padding: 24px;
    gap: 14px;
}
title {
    color: var(--text);
    font-size: 28px;
    font-weight: bold;
}
lead {
    color: var(--text-secondary);
    font-size: 15px;
    line-height: 1.5;
}
cook_card, ticket_card, way_card, film_card {
    background-color: var(--surface);
    border-radius: 18px;
    padding: 18px 4px;
    gap: 4px;
}
cook_kicker, ticket_kicker, way_kicker, film_kicker {
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
cook_name, film_name {
    color: var(--text);
    font-size: 20px;
    font-weight: bold;
}
ticket_name {
    color: var(--text);
    font-size: 34px;
    font-weight: bold;
}
cook_note, ticket_note, way_note, film_note {
    color: var(--text-secondary);
    font-size: 14px;
}
cook_actions, way_actions {
    padding: 0px 16px;
    margin-top: 12px;
}
ticket_actions, film_actions {
    display: flex;
    flex-direction: row;
    align-items: center;
    padding: 0px 0px 0px 16px;
    margin-top: 12px;
}
show, watch {
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 24px;
}
player {
    background-color: #0B0D12;
    padding: 32px;
    gap: 6px;
}
now_kicker {
    color: #9AA3B2;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 1.2px;
}
now_title {
    color: #FFFFFF;
    font-size: 30px;
    font-weight: bold;
}
now_time {
    color: #9AA3B2;
    font-size: 15px;
}
player_actions {
    display: flex;
    flex-direction: row;
    align-items: center;
    padding: 0px 0px 0px 16px;
    margin-top: 16px;
}
close {
    color: #FFFFFF;
    border-color: #5B6474;
    border-radius: 24px;
    min-height: 48px;
    padding: 0px 24px;
}
"""

run(start_screen=home, theme=theme, orientation="portrait")
