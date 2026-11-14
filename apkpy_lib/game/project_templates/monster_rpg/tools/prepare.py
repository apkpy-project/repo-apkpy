"""Everything the content needs before the game is built, in order. The build runs this for you (apkpy.toml: before_build).

    python tools/prepare.py

It draws missing art, turns story/ into events and maps_src/ into maps/, and checks that everything points at something that exists.
"""
import make_art
import map_tool
import story_tool
import validate_data


def main():
    validate_data.check_json_files()
    make_art.main()
    story_tool.main()
    map_tool.main([])
    found = validate_data.check()
    for problem in found:
        print(problem)
    if found:
        raise SystemExit("%d problem(s) in the content." % len(found))
    for note in validate_data.notes():
        print("note: " + note)


if __name__ == "__main__":
    main()
