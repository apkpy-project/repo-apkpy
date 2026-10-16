# -*- coding: utf-8 -*-
"""The shared icon catalogue, and the geometry both runtimes draw from it."""

import io
import os
import shutil
import tempfile
import unittest

import _layout
from apkpy_lib import icons
from apkpy_lib.core.compiler import _material_icon_path, _icon_path_data


def _ink(name_or_data, size=22, supersample=3):
    data = icons.resolve(name_or_data) or name_or_data
    coverage = icons.rasterize(icons.flatten(data), size, supersample=supersample)
    return sum(1 for value in coverage if value > 40) / float(size * size)


class CatalogueParityTests(unittest.TestCase):
    """The point of the module: the two backends cannot disagree."""

    def test_both_backends_resolve_the_same_geometry(self):
        for name in icons.names():
            self.assertEqual(_material_icon_path(name), icons.resolve(name), name)

    def test_unknown_name_falls_back_identically_on_both_sides(self):
        self.assertIsNone(icons.resolve('definitely_not_an_icon'))
        self.assertEqual(
            _material_icon_path('definitely_not_an_icon'),
            icons.resolve(icons.FALLBACK_ICON),
        )

    def test_names_that_used_to_render_as_a_circle_now_exist(self):
        # Seven had no drawing in the Previewer, twelve none on Android, and
        # nine more were used by ApkPy's own examples with no drawing anywhere.
        for name in ('person', 'camera', 'chart', 'message',
                     'skip_next', 'skip_previous', 'warning', 'volume_off',
                     'attach_file', 'checklist', 'delete_sweep', 'done_all',
                     'inventory_2', 'library_music', 'note_add', 'repeat',
                     'shuffle'):
            self.assertIsNotNone(icons.resolve(name), name)
            self.assertNotEqual(
                icons.resolve(name), icons.resolve('circle'), name)

    def test_aliases_reach_a_real_icon(self):
        self.assertEqual(icons.resolve('favorite'), icons.resolve('heart'))
        self.assertEqual(icons.resolve('notifications'), icons.resolve('bell'))
        self.assertEqual(icons.resolve('replay_5'), icons.resolve('replay'))
        self.assertEqual(icons.resolve('photo'), icons.resolve('image'))

    def test_suggestion_finds_the_obvious_typo(self):
        self.assertEqual(icons.suggest('seting'), 'settings')
        self.assertEqual(icons.suggest('persn'), 'person')
        self.assertIsNone(icons.suggest('zzzzzzzzzz'))


def _alpha_mass(data, size=48):
    """Ink measured as alpha mass, not thresholded pixels.

    A thin outline is mostly antialiased edge, so counting pixels above a
    threshold makes it look *heavier* than the filled shape at small sizes.
    """
    coverage = icons.rasterize(icons.flatten(data), size, supersample=2)
    return sum(coverage) / float(size * size * 255)


class OutlinedVariantTests(unittest.TestCase):
    def test_every_outlined_variant_is_lighter_than_its_filled_form(self):
        # This is what "outlined" means, and it catches a variant pasted in
        # from the wrong icon.
        for name in icons.names():
            if not icons.has_outlined(name):
                continue
            outline = _alpha_mass(icons.resolve(name, 'outlined'))
            filled = _alpha_mass(icons.resolve(name))
            self.assertLess(outline, filled, name)

    def test_every_outlined_variant_draws_something(self):
        for name in icons.names():
            if not icons.has_outlined(name):
                continue
            self.assertGreater(_alpha_mass(icons.resolve(name, 'outlined')),
                               0.05, name)

    def test_a_name_without_a_variant_falls_back_to_filled(self):
        self.assertFalse(icons.has_outlined('search'))
        self.assertEqual(icons.resolve('search', 'outlined'),
                         icons.resolve('search'))
        self.assertEqual(icons.path_for('search', 'outlined'),
                         icons.resolve('search'))

    def test_the_navigation_names_carry_a_variant(self):
        for name in ('home', 'person', 'settings', 'star', 'heart', 'folder'):
            self.assertTrue(icons.has_outlined(name), name)

    def test_unknown_name_still_falls_back_to_circle_in_either_style(self):
        self.assertEqual(icons.path_for('nope', 'outlined'),
                         icons.resolve('circle'))

    def test_the_single_argument_form_still_works(self):
        # Every existing call site passes one argument.
        self.assertEqual(icons.resolve('home'), icons.resolve('home', 'filled'))


class GeometryTests(unittest.TestCase):
    def test_every_icon_parses_and_covers_a_plausible_area(self):
        for name in icons.names():
            ink = _ink(name)
            self.assertTrue(0.05 < ink < 0.95, '%s covers %.3f' % (name, ink))

    def test_fill_rule_is_nonzero_so_holes_are_cut(self):
        gear = icons.rasterize(icons.flatten(icons.resolve('settings')), 24)
        self.assertLess(gear[12 * 24 + 12], 40, 'the gear lost its centre hole')

    def test_nonzero_does_not_punch_a_hole_where_subpaths_overlap(self):
        # library_music's back card overlaps its front card in the same
        # direction. Even-odd would cancel them out and leave a hole there.
        card = icons.rasterize(icons.flatten(icons.resolve('library_music')), 24)
        self.assertGreater(card[15 * 24 + 6], 200)

    def test_rasterize_is_antialiased(self):
        # A hand-drawn canvas polygon is binary; the whole visual complaint was
        # that edges looked jagged. Partial coverage is the proof it no longer is.
        coverage = icons.rasterize(icons.flatten(icons.resolve('circle')), 24)
        partial = [value for value in coverage if 20 < value < 235]
        self.assertGreater(len(partial), 20)

    def test_curves_and_arcs_reach_the_same_shape(self):
        # A circle drawn with cubics and one drawn with arcs must agree.
        cubic = icons.rasterize(icons.flatten(icons.resolve('circle')), 24)
        arced = icons.rasterize(icons.flatten(
            'M12,2A10,10 0 1 1 11.99,2 Z'), 24)
        differing = sum(1 for a, b in zip(cubic, arced) if abs(a - b) > 90)
        self.assertLess(differing, 24)

    def test_empty_and_degenerate_input_is_survivable(self):
        self.assertEqual(icons.flatten('M0,0'), [])
        self.assertEqual(len(icons.rasterize([], 8)), 64)
        self.assertEqual(icons.rasterize([], 0), bytearray())

    def test_malformed_path_data_is_rejected_with_a_readable_message(self):
        for bad in ('M1,1 L', 'Q what', '5,5 L2,2'):
            with self.assertRaises(ValueError):
                icons.flatten(bad)

    def test_to_path_data_drops_points_on_a_straight_run(self):
        straight = [[(0.0, 0.0), (4.0, 0.0), (8.0, 0.0),
                     (8.0, 8.0), (0.0, 8.0), (0.0, 0.0)]]
        emitted = icons.to_path_data(straight)
        self.assertEqual(emitted.count('L'), 3)


class UserSvgTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix='apkpy_icons_')
        self.addCleanup(shutil.rmtree, self.folder, True)

    def _write(self, name, body):
        path = os.path.join(self.folder, name)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(body)
        return path

    def test_viewbox_is_rescaled_to_the_24_grid(self):
        path = self._write('big.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96">'
            '<rect x="24" y="24" width="48" height="48" fill="#000"/></svg>')
        coverage = icons.rasterize(icons.flatten(icons.load_svg(path)), 24)
        self.assertGreater(coverage[12 * 24 + 12], 200)   # centre is filled
        self.assertLess(coverage[1 * 24 + 1], 40)         # corner is not

    def test_nested_transforms_are_applied(self):
        flat = self._write('flat.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path d="M2,11 H22 V13 H2 Z" fill="#000"/></svg>')
        turned = self._write('turned.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<g transform="translate(12,12) rotate(90) translate(-12,-12)">'
            '<path d="M2,11 H22 V13 H2 Z" fill="#000"/></g></svg>')
        horizontal = icons.rasterize(icons.flatten(icons.load_svg(flat)), 24)
        vertical = icons.rasterize(icons.flatten(icons.load_svg(turned)), 24)
        self.assertGreater(horizontal[12 * 24 + 3], 200)  # bar runs across
        self.assertLess(vertical[12 * 24 + 3], 40)        # rotated away
        self.assertGreater(vertical[3 * 24 + 12], 200)    # now runs down

    def test_basic_shapes_are_converted(self):
        path = self._write('shapes.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<rect x="2" y="2" width="20" height="20" rx="4" fill="#000"/>'
            '<circle cx="12" cy="12" r="5" fill="#fff"/></svg>')
        coverage = icons.rasterize(icons.flatten(icons.load_svg(path)), 24)
        self.assertLess(coverage[12 * 24 + 12], 40)       # circle cut out
        self.assertGreater(coverage[4 * 24 + 12], 200)    # rect body filled

    def test_a_second_fill_colour_is_cut_out_not_merged(self):
        # Designers fake a hole by painting a white shape on top of a dark one.
        # A browser paints in order so it looks right; a single-colour
        # silhouette would swallow it, and the detail would just disappear.
        path = self._write('two_tone.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path d="M2,2 h20 v20 h-20 z" fill="#111"/>'
            '<path d="M9,9 h6 v6 h-6 z" fill="#ffffff"/></svg>')
        coverage = icons.rasterize(icons.flatten(icons.load_svg(path)), 24)
        self.assertLess(coverage[12 * 24 + 12], 40, 'the white shape merged in')
        self.assertGreater(coverage[5 * 24 + 12], 200, 'the body was lost')

    def test_a_single_colour_svg_is_unaffected_by_the_two_tone_rule(self):
        path = self._write('one_tone.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<path d="M2,2 h9 v20 h-9 z" fill="#111"/>'
            '<path d="M13,2 h9 v20 h-9 z" fill="#111"/></svg>')
        coverage = icons.rasterize(icons.flatten(icons.load_svg(path)), 24)
        self.assertGreater(coverage[12 * 24 + 5], 200)
        self.assertGreater(coverage[12 * 24 + 18], 200)

    def test_the_demo_brand_mark_still_reads_as_a_shape(self):
        here = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        mark = os.path.join(here, 'playground', 'assets', 'market_mark.svg')
        if not os.path.exists(mark):
            self.skipTest('demo asset not present')
        ink = _ink(icons.load_svg(mark))
        self.assertTrue(0.15 < ink < 0.75, ink)

    def test_polygon_is_converted(self):
        path = self._write('poly.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<polygon points="12,2 22,22 2,22" fill="#000"/></svg>')
        self.assertGreater(_ink(icons.load_svg(path)), 0.2)

    def test_stroke_only_svg_explains_how_to_fix_it(self):
        path = self._write('stroke.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<circle cx="12" cy="12" r="8" fill="none" stroke="#000"/></svg>')
        with self.assertRaises(ValueError) as caught:
            icons.load_svg(path)
        self.assertIn('Outline stroke', str(caught.exception))

    def test_unconvertible_element_is_named(self):
        path = self._write('text.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<text x="2" y="12">hi</text></svg>')
        with self.assertRaises(ValueError) as caught:
            icons.load_svg(path)
        self.assertIn('<text>', str(caught.exception))

    def test_missing_file_says_so(self):
        with self.assertRaises(ValueError) as caught:
            icons.load_svg(os.path.join(self.folder, 'nope.svg'))
        self.assertIn('not found', str(caught.exception))

    def test_broken_xml_is_reported_as_invalid_svg(self):
        path = self._write('broken.svg', '<svg><rect')
        with self.assertRaises(ValueError) as caught:
            icons.load_svg(path)
        self.assertIn('not valid SVG', str(caught.exception))

    def test_is_file_reference_only_matches_files(self):
        for value in ('logo.svg', 'assets/logo.svg', 'a\\b.svg', 'x/y'):
            self.assertTrue(icons.is_file_reference(value), value)
        for value in ('settings', 'arrow_back', '', None):
            self.assertFalse(icons.is_file_reference(value), value)

    def test_compiler_emits_flattened_geometry_for_a_user_file(self):
        path = self._write('logo.svg',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '<circle cx="12" cy="12" r="9" fill="#000"/></svg>')
        emitted = _icon_path_data(path)
        # Flattened, so the phone draws the very points the Previewer drew.
        self.assertIn('L', emitted)
        self.assertNotIn('A', emitted)
        self.assertNotIn('C', emitted)


class DiagnosticsTests(unittest.TestCase):
    def test_svg_failures_map_to_their_own_codes(self):
        from apkpy_lib.diagnostics import diagnose_exception
        cases = (
            ('icon file not found: a.svg', 'U2016'),
            ('icon file a.svg draws with strokes and no fill', 'U2017'),
            ('icon file a.svg uses <text>, which ApkPy cannot convert '
             'to a vector icon', 'U2018'),
            ('icon file a.svg is not valid SVG: x', 'U2019'),
            ('icon path data has an unexpected character', 'U2019'),
            ('action(icon=...) requires a Material icon name', 'U2011'),
        )
        for message, code in cases:
            self.assertEqual(
                diagnose_exception(ValueError(message)).code, code, message)

    def test_empty_technical_section_is_omitted(self):
        from apkpy_lib.diagnostics import Diagnostic, render_diagnostic
        rendered = render_diagnostic(Diagnostic(
            code='U2015', title='t', message='m', cause='c'))
        self.assertNotIn('Technical details', rendered)


class TheNamesWeShipTests(unittest.TestCase):
    """Every icon named in an example or a guide has to exist.

    A name the catalogue does not know is drawn as a plain circle on both
    runtimes. That is deliberate -- there is nothing else to draw -- and it is
    also invisible: it reads as a design choice, not a typo. U2015 says so at
    build time, and a build prints a lot of lines. Four of these reached the
    published showcase APKs, where a finance app had a circle for "Cards".
    """

    PATTERNS = (
        r'icons?\s*=\s*"([a-z0-9_]+)"',
        r'"icon"\s*:\s*"([a-z0-9_]+)"',
        r'icons\s*=\s*\[([^\]]*)\]',
    )

    def _sources(self):
        found = [str(path) for path in _layout.examples().rglob('*.py')]
        # The guides are the site's source, which is not in every checkout.
        if _layout.site_docs() is not None:
            for pattern in ('*.md', '*.py'):
                found += [str(path) for path in _layout.site_docs().rglob(pattern)]
        return sorted(set(found))

    @unittest.skipUnless(_layout.examples(), 'the examples are not in this checkout')
    def test_every_icon_named_in_the_repository_exists(self):
        import re
        # ApkPy's own glyphs and the whole Material Icons set: any name in it
        # draws on both runtimes.
        catalogue = set(icons.all_names())
        self.assertTrue(catalogue, 'the catalogue did not load')
        self.assertTrue(set(getattr(icons, '_ICON_PATHS', {}) or {}) <= catalogue)
        unknown = {}
        for path in self._sources():
            with io.open(path, encoding='utf-8', errors='replace') as handle:
                body = handle.read()
            names = []
            for index, pattern in enumerate(self.PATTERNS):
                for match in re.finditer(pattern, body):
                    names += (re.findall(r'"([a-z0-9_]+)"', match.group(1))
                              if index == 2 else [match.group(1)])
            for name in names:
                if name and name not in catalogue \
                        and not name.endswith(('svg', 'png')):
                    unknown.setdefault(name, set()).add(
                        os.path.relpath(path, str(_layout.ROOT)))
        self.assertFalse(unknown, 'nomes fora do catalogo: ' + '; '.join(
            '%s (%s)' % (name, ', '.join(sorted(where)))
            for name, where in sorted(unknown.items())))

if __name__ == '__main__':
    unittest.main()
