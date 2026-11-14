"""A value of the app, written as Java: a name, a call, a field's text, an item of a list."""
import ast
import json
import re

from ...features import choice as choice_feature
from ...features import field as field_feature
from ...features import web_page as web_page_feature
from ...features import rich_content as rich_content_feature
from ...features import feeds as feeds_feature
from ...features import native as native_feature
from ...features import flashlight as flashlight_feature
from ...features import draw_pad as draw_pad_feature
from ...features import pending_views as pending_views_feature
from ...features import wallpaper as wallpaper_feature
from ...features import sensors as sensors_feature
from ...features import view_state as view_state_feature
from ...features import regex as regex_feature
from ...features import unpacking as unpacking_feature
from ...features import tuples as tuples_feature
from ...features import item_assignment as item_feature
from ...features import classes as classes_feature
from ...features import sets as sets_feature
from ...features import counters as counters_feature
from ...features import function_values as function_values_feature
from ...features import notifications as notifications_feature
from ...features import camera as camera_feature
from ... import unsupported
from ... import i18n as i18n_feature
from ..state import _ELSEWHERE_EMPTY, _GLOBALS, _I18N, _MUTATED_LISTS, _VIEW_COMPS, _VIEW_OWNERS
from ..style import _java_int_literal
from ..kinds import _int_literal, _json_call, _kind_from, _static_kind
from ..expressions import (
    _shown_raw_java,
    _add_java, _affix_java, _arith_any_java, _callback_call_args, _check_translation_key,
    _collection_item_java_literal, _cond_shape_supported, _cond_to_java, _counter_call_java,
    _datetime_call_to_java, _delitem_java, _dict_method_java, _emit_json_set_collection_items,
    _escape_java_literal, _extreme_by_java, _format_kind, _formatted_java, _fstring_node_to_java,
    _has_sort_keys, _index_java, _is_isinstance, _isinstance_java, _json_module_java,
    _json_node_to_java, _json_value_java, _len_java, _list_call_java, _list_row_java_literal,
    _listop_java, _logic_value_java, _math_java, _may_be_singleton, _mutated_list_read,
    _negate_any_java, _numeric_call_java, _percent_java, _repeat_java, _rich_set_value_java,
    _round_java, _set_call_java, _setitem_java, _slice_java, _sorted_java, _split_java,
    _sql_params_java, _str_format_java, _ternary_to_java, _text_method_java, _truthy_java,
    _typed_operand, _unpack_java, _written_out,
)
from ..statements import _assign_rhs_java, _emit_json_set_items
from ..numeric import (
    _ARITH_OPS, _arith_java, _bool_operand, _dict_copy_call, _float_call_java, _int_call_java,
)
from ..prescan import _global_read


class Values:
    """A value of the app, written as Java: a name, a call, a field's text, an item of a list."""

    def _get_jv_from_py_var(self, py_var):
        for c in self.all_comps_flat:
            if c.get('_py_var') == py_var:
                return c.get('_java_var')
        return None

    def _get_comp_from_py_var(self, py_var):
        for component in self.all_comps_flat:
            if component.get('_py_var') == py_var:
                return component
        return None

    def _field_box_of(self, py_var):
        """The id of the ApkpyField around a field of this screen, or None:
        a plain field has none, and a field of another screen is not here."""
        component = self._get_comp_from_py_var(py_var)
        if field_feature.boxed(component) and component.get('_java_var'):
            return field_feature.box_id(component['_java_var'])
        return None

    def _visible_view_of(self, py_var):
        """The view hide() and show() act on. A field with words under it
        goes with them, so it is the box and not the EditText."""
        return self._field_box_of(py_var) or self._get_jv_from_py_var(py_var)

    def _pending_put(self, indent, command, kind, value_java):
        """A write to a component that lives on another screen: left in
        ApkpyPending for that screen, instead of dropped (it used to be)."""
        owner = _VIEW_OWNERS[0].get(command.get('py_var'))
        if owner and owner != self.screen_id:
            self.lines.append(pending_views_feature.put_line(
                indent, owner, command['py_var'], kind, value_java))

    def _emit_fill_items(self, indent, jv, c, is_virtual, rich):
        """The rows a set_items call puts in {jv}_items -- the same whether
        the list is on this screen or waits for its own (pending_views)."""
        lines = self.lines
        items_node = c.get('items_node')
        # Written out to the last value, the rows are Java literals. A row
        # that holds a name -- set_items([{"title": text}]) -- is worked out
        # while the app runs, as a list built with append() is: here it was
        # "{}", an empty row, and a name on its own was left out.
        if items_node and isinstance(items_node, ast.List) \
                and _written_out(items_node):
            for elt in items_node.elts:
                if isinstance(elt, ast.Constant):
                    if is_virtual:
                        lines.append(
                            f'{indent}{jv}_items.add('
                            f'{_collection_item_java_literal(elt.value)});'
                        )
                    else:
                        lines.append(f'{indent}{jv}_items.add({_list_row_java_literal(elt.value, rich)});')
                elif isinstance(elt, ast.Dict):
                    if is_virtual:
                        try:
                            literal_item = ast.literal_eval(elt)
                        except (ValueError, TypeError, SyntaxError):
                            literal_item = {}
                        lines.append(
                            f'{indent}{jv}_items.add('
                            f'{_collection_item_java_literal(literal_item)});'
                        )
                        continue
                    _row = {}
                    for k, v in zip(elt.keys, elt.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                            _row[str(k.value)] = v.value
                    lines.append(f'{indent}{jv}_items.add({_list_row_java_literal(_row, rich)});')
        elif items_node is not None:
            # Expressão dinâmica (variável JSON de db.query/https)
            if is_virtual:
                _emit_json_set_collection_items(
                    lines, indent, jv, self._val_to_java(items_node),
                    id(c) & 0xFFFF,
                )
            else:
                _emit_json_set_items(lines, indent, jv, self._val_to_java(items_node),
                                     c.get('title_key'), c.get('subtitle_key'), id(c) & 0xFFFF,
                                     image_key=c.get('image_key'), rich=rich)

    def _pending_put_items(self, indent, command):
        """set_items on another screen's list: the rows are normalised here,
        by the same code the list's own screen runs, and left for it."""
        lines = self.lines
        owner = _VIEW_OWNERS[0].get(command.get('py_var'))
        if not owner or owner == self.screen_id:
            return
        target = _VIEW_COMPS[0].get(command['py_var']) or {}
        is_virtual = target.get('comp_type') == 'virtual_collection'
        inner = indent + "    "
        lines.append(f"{indent}{{")
        lines.append(f"{inner}java.util.ArrayList<String> _apkpyPend_items = new java.util.ArrayList<>();")
        self._emit_fill_items(inner, "_apkpyPend", command, is_virtual, bool(target.get('rich')))
        if is_virtual and feeds_feature.is_paginated(target):
            _has_more = command.get('has_more_node')
            lines.append(pending_views_feature.put_line(
                inner, owner, command['py_var'], pending_views_feature.HAS_MORE,
                self._val_to_java(_has_more) if _has_more is not None else 'true'))
        lines.append(pending_views_feature.put_line(
            inner, owner, command['py_var'], pending_views_feature.ITEMS,
            "new org.json.JSONArray(_apkpyPend_items).toString()"))
        lines.append(f"{indent}}}")

    def _emit_set_value_by_id(self, indent, comp_dict, jv, val_java, node=None):
        """set_value on a view reached through findViewById -- the form a
        method uses, as opposed to onCreate's local variables."""
        lines = self.lines
        ctype = comp_dict.get('comp_type', '')
        itype = comp_dict.get('input_type', 'text') if ctype in ('inputs', 'input_field') else ''
        if ctype in choice_feature.COMPONENTS:
            lines.append(indent + choice_feature.set_java(jv, val_java))
            return
        if ctype == web_page_feature.COMPONENT:
            lines.append(indent + web_page_feature.set_java(jv, val_java))
            return
        if ctype in rich_content_feature.COMPONENT_NAMES:
            lines.append(_rich_set_value_java(indent, ctype, jv, val_java, node))
            return
        if ctype == 'chart':
            # A ring's value: the chart is no TextView, and a cast to one
            # compiled and threw ClassCastException when it ran.
            lines.append(
                f'{indent}((ApkpyChart) findViewById(R.id.{jv}))'
                f'.setValue(Float.parseFloat(String.valueOf({val_java})));')
        elif ctype == 'list_row':
            lines.append(
                f'{indent}((android.widget.TextView)findViewById('
                f'R.id.{jv}_title)).setText(String.valueOf({val_java}));'
            )
        elif itype == 'radio':
            placeholder = comp_dict.get('placeholder', '')
            options = [o.strip() for o in placeholder.split('|')] if placeholder else []
            for i, opt in enumerate(options):
                rb_id = f"{jv}_rb{i}"
                kw = 'if' if i == 0 else 'else if'
                lines.append(f"{indent}{kw} ({val_java}.equals(\"{opt}\")) ((android.widget.RadioGroup)findViewById(R.id.{jv}Group)).check(R.id.{rb_id});")
        elif itype == 'switch':
            lines.append(f"{indent}((androidx.appcompat.widget.SwitchCompat)findViewById(R.id.{jv})).setChecked(String.valueOf({val_java}).equals(\"true\"));")
        elif itype == 'checkbox':
            lines.append(f"{indent}if (String.valueOf({val_java}).equals(\"true\")) ((android.widget.CheckBox)findViewById(R.id.{jv})).setChecked(true);")
            lines.append(f"{indent}else ((android.widget.CheckBox)findViewById(R.id.{jv})).setChecked(false);")
        elif itype == 'select':
            placeholder_local = comp_dict.get('placeholder', '')
            options = [o.strip() for o in placeholder_local.split('|')] if placeholder_local else []
            for i, opt in enumerate(options):
                kw = 'if' if i == 0 else 'else if'
                lines.append(f"{indent}{kw} ({val_java}.equals(\"{opt}\")) ((android.widget.Spinner)findViewById(R.id.{jv})).setSelection({i});")
        elif itype == 'range':
            lines.append(f"{indent}try {{ ((android.widget.SeekBar)findViewById(R.id.{jv})).setProgress(Integer.parseInt(String.valueOf({val_java}))); }} catch (Exception _e_{jv}) {{}}")
        elif itype in ('text', 'password', 'search', 'textarea', 'number'):
            lines.append(f"{indent}((android.widget.EditText)findViewById(R.id.{jv})).setText(String.valueOf({val_java}));")
        else:
            lines.append(f"{indent}((android.widget.TextView)findViewById(R.id.{jv})).setText(String.valueOf({val_java}));")
        view_state_feature.remember(lines, indent, comp_dict, jv)

    def _state_method_name(self, state_var):
        safe = re.sub(r'[^A-Za-z0-9_]', '_', str(state_var))
        if not safe or safe[0].isdigit():
            safe = '_' + safe
        return f"_renderReactiveState_{safe}"

    def _state_key_literal(self, state_var):
        info = self.reactive_states.get(state_var, {})
        return _escape_java_literal(str(info.get('id', state_var)))

    def _numeric_java_expr(self, node):
        """Se o nó for uma expressão puramente numérica (int(...)/float(...), literais
        numéricos e + - * / % entre elas), devolve o par (expressão Java, is_float);
        caso contrário None. Serve para distinguir 'int(x) + 1' (soma numérica) de
        '"a" + b' (concatenação) — ambas usam ast.Add — e para emitir aritmética
        com semântica Python (ex.: '/' é SEMPRE divisão float)."""
        if isinstance(node, ast.Name) and node.id in self._numeric_vars:
            # variável local já conhecida como número (preserva int vs float)
            _ref = _global_read(node.id) if node.id in _GLOBALS[0] else node.id
            if self._numeric_vars[node.id]:
                return (f"Double.parseDouble(String.valueOf({_ref}))", True)
            return (f"Long.parseLong(String.valueOf({_ref}))", False)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'int':
            return (_int_call_java(node, self._numeric_java_expr, self._val_to_java), False)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'float':
            return (_float_call_java(node, self._numeric_java_expr, self._val_to_java), True)
        _nc = _numeric_call_java(node, self._numeric_java_expr, self._val_to_java)
        if _nc is not None:
            return _nc
        if isinstance(node, ast.Constant) and isinstance(node.value, bool):
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return (_java_int_literal(node.value, node), False)
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            return (str(node.value), True)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            # -x: o sinal de um numero que ja se sabe ser numero.
            inner = self._numeric_java_expr(node.operand)
            if inner is None:
                return None
            if isinstance(node.op, ast.USub) and not inner[1]                     and _int_literal(node.operand) is None:
                # -n de um int: o menor long trocado de sinal dava-se a si
                # proprio; os ints do Python nao tem esse fundo.
                return (f"Math.negateExact((long)({inner[0]}))", False)
            sign = '-' if isinstance(node.op, ast.USub) else '+'
            return (f"({sign}{inner[0]})", inner[1])
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
            # ~n of an int is -(n + 1) in Python and in Java's long alike.
            inner = self._numeric_java_expr(node.operand)
            if inner is None or inner[1]:
                return None
            return (f"(~((long)({inner[0]})))", False)
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
            left = _bool_operand(node.left) or self._numeric_java_expr(node.left)
            right = _bool_operand(node.right) or self._numeric_java_expr(node.right)
            if left is None or right is None:
                return None
            return _arith_java(node.op, left, right, node.right)
        if isinstance(node, ast.IfExp):
            # Both sides the same kind of number (see _numeric_arg_kind).
            yes = self._numeric_java_expr(node.body)
            no = self._numeric_java_expr(node.orelse)
            if yes is None or no is None or yes[1] != no[1] \
                    or not _cond_shape_supported(node.test):
                return None
            cond = _cond_to_java(node.test, self._val_to_java, self._cur_bool_args[0])
            if not cond:
                return None
            return (f"({cond} ? {yes[0]} : {no[0]})", yes[1])
        return None

    def _val_to_java(self, node):
        import ast
        if field_feature.is_check_call(node):
            return field_feature.value_java(node, self._field_box_of)
        if notifications_feature.is_value_call(node):
            return notifications_feature.value_java(node)
        if regex_feature.internal(node):
            return regex_feature.java_value(node, self._val_to_java)
        if sets_feature.op_of(node) is not None:
            return _set_call_java(node, self._val_to_java)
        if counters_feature.op_of(node) is not None:
            return _counter_call_java(node, self._val_to_java)
        if function_values_feature.internal(node) == function_values_feature.FN:
            # A function handed on as a value: its name.
            return '"%s"' % node.args[0].value
        if function_values_feature.internal(node) == function_values_feature.CALL:
            return "_apkpyCall(%s)" % ", ".join(
                "String.valueOf(%s)" % self._val_to_java(a) for a in node.args)
        if _dict_copy_call(node, self._val_to_java):
            # dict(d): a copy, as d.copy() is.
            return self._val_to_java(ast.copy_location(ast.Call(
                func=ast.Attribute(value=node.args[0], attr='copy', ctx=ast.Load()),
                args=[], keywords=[]), node))
        if classes_feature.is_intrinsic(node):
            return classes_feature.value_java(node, self._val_to_java, _assign_rhs_java)
        if node is None:
            return '""'
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return f'"{_escape_java_literal(node.value)}"'
            elif isinstance(node.value, bool):
                return 'true' if node.value else 'false'
            elif node.value is None:
                return "ApkpyValues.NONE"
            if isinstance(node.value, int):
                return _java_int_literal(node.value, node)
            if isinstance(node.value, (bytes, complex)) or node.value is Ellipsis:
                # b"abc" went out as b'abc', 2j as 2j: Java has neither, and
                # javac stopped far from the line that wrote them.
                unsupported.raise_unsupported(
                    node, cause="bytes (b\"...\"), complex numbers (2j) and ... as a value "
                                "are not translated yet. Text on the phone is a str.",
                    suggestions=["Write text instead: \"abc\"."])
            return str(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(
                node.op, (ast.USub, ast.UAdd, ast.Invert)):
            try:
                literal = ast.literal_eval(node)
                if isinstance(literal, (int, float)) and not isinstance(literal, bool):
                    return str(literal)
            except (TypeError, ValueError, SyntaxError):
                pass
            _ne = self._numeric_java_expr(node)
            if _ne is not None:
                return f"_apkpyFloat({_ne[0]})" if _ne[1] else f"String.valueOf({_ne[0]})"
            if unsupported.reaches_other_runtime(node):
                return '""'
            _rt = _negate_any_java(node, self._val_to_java)
            if _rt is not None:
                return _rt
            # -n de um texto voltava como "", sem uma palavra.
            unsupported.raise_untranslated_arithmetic(node)
        # ast.Str / ast.Num were these Constants until Python 3.13; 3.14 removed them.
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            return f'"{_escape_java_literal(node.value)}"'
        elif (isinstance(node, ast.Constant) and isinstance(node.value, (int, float, complex))
              and not isinstance(node.value, bool)):
            return str(node.value)
        elif isinstance(node, ast.Name):
            # Uma lista de modulo a que a app faz append vive no estado
            # partilhado: inlinar o literal aqui daria sempre a lista de
            # origem, por muito que ela tivesse crescido.
            if node.id in _MUTATED_LISTS[0]:
                return _mutated_list_read(node.id)
            if node.id in _GLOBALS[0]:
                return _global_read(node.id)
            return node.id
        elif isinstance(node, ast.IfExp):
            return _ternary_to_java(node, self._val_to_java, self._cur_bool_args[0]) or unsupported.raise_untranslated_condition(node.test)
        elif isinstance(node, (ast.List, ast.Tuple)):
            # Lista Python → array JSON em runtime (iterável com `for x in xs:`).
            # Passa pelo mesmo conversor do dict para que uma lista de objetos
            # continue a ser uma lista de objetos: o `asList(String.valueOf(...))`
            # que aqui estava punha cada `{...}` entre aspas, como texto.
            # Um tuplo e' o mesmo aqui: `return total, count` devolvia vazio,
            # e stats()[0] lia de nada.
            return _json_node_to_java(
                node, self._val_to_java, self._json_struct_vars) + ".toString()"
        elif isinstance(node, ast.Dict):
            # Dicionário Python → objeto JSON. Sem este ramo caía no `""` do
            # fim: o corpo de um https.post desaparecia em silêncio, e um
            # `body = {...}` nem sequer chegava a ser declarado em Java.
            return _json_node_to_java(
                node, self._val_to_java, self._json_struct_vars) + ".toString()"
        elif isinstance(node, ast.Subscript):
            slice_node = node.slice
            # texto[0:2] — uma fatia saía daqui como `(x)[Integer.parseInt("")]`,
            # que nem é Java: o build morria com um erro de sintaxe longe daqui,
            # ou pior, não morria. Apanhada na origem em vez de na guarda final.
            if isinstance(slice_node, ast.Slice):
                # texto[a:b]. O Python apara fora dos limites e conta do fim
                # com indices negativos; o substring do Java rebenta. O helper
                # tem as regras do Python, para os dois lados responderem o
                # mesmo em vez de um devolver texto e o outro fechar a app.
                return _slice_java(node, self._val_to_java)
            if isinstance(slice_node, ast.Index):  # Python 3.8 compat
                slice_node = slice_node.value
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                base = self._val_to_java(node.value)
                key = slice_node.value
                # row["k"] dentro de `for row in rows:` — row é texto JSON
                if isinstance(node.value, ast.Name) and node.value.id in self._json_iter_vars:
                    key_esc = key.replace('"', '\\"')
                    return f'_jsonGet(String.valueOf({base}), "{key_esc}")'
                # itens[0]["title"] — o que sai do _apkpyListGet e' o texto de
                # um objeto JSON, nao uma linha de list_view. A heuristica do
                # travessao la' em baixo devolveria o objeto inteiro.
                # Any other name: a key in text is always the read of a
                # record. This branch used to guess that the value was a
                # list_view row's "title — subtitle" text, and for every
                # other key handed back the whole value: `first["name"]`
                # after `first = rows[0]`, a dict written in the source, a
                # json_get() result, a tapped row's "id" -- all of them the
                # entire record, on the phone only, without a word. A
                # list_view row is a record now too (_list_row_java_literal).
                key_esc = key.replace('"', '\\"')
                return f'_jsonGet(String.valueOf({base}), "{key_esc}")'
            # lista[0] saia daqui como `(x)[Integer.parseInt(...)]`, que nao e
            # Java: nao se indexa uma String com parentesis retos. E uma lista
            # aqui e texto JSON, por isso quem sabe le-la e o helper.
            return _index_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in self.reactive_states \
                and node.func.attr == 'get':
            state_var = node.func.value.id
            state_info = self.reactive_states[state_var]
            default_expr = self._val_to_java(state_info.get('initial_node'))
            return (
                f'ApkpyReactiveState.get("{self._state_key_literal(state_var)}", '
                f'String.valueOf({default_expr}))'
            )
        elif (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'get'
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == 'storage'):
            # storage.get(k, d) inside an expression rather than on its
            # own line. Without this it fell through to "" in silence --
            # the failure mode this compiler pays the most for, because
            # the Previewer reads the value and the phone reads nothing.
            _sk = self._val_to_java(node.args[0]) if node.args else '""'
            _sd = None
            if len(node.args) > 1:
                _sd = node.args[1]
            else:
                for _kw in node.keywords:
                    if _kw.arg == 'default':
                        _sd = _kw.value
            return ('_apkpyStorageGet(String.valueOf(%s), String.valueOf(%s))'
                    % (_sk, self._val_to_java(_sd)))
        # appearance.get() -- o modo em vigor, para uma linha poder dizer
        # qual esta' escolhido. O default e' o que o Theme declarou.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == 'get'
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'appearance'):
            return ('_apkpyStorageGet("__apkpy_appearance", '
                    '_apkpyDeclaredAppearance())')
        # app.version_code() / app.version_name() -- lidos do pacote
        # INSTALADO, por isso sao a versao que esta mesmo a correr e
        # nao a que o codigo-fonte esperava.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr in ('version_code', 'version_name')
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'app'):
            return ('_apkpyVersionCode()' if node.func.attr == 'version_code'
                    else '_apkpyVersionName()')
        # pad.is_empty() / pad.save(name): the draw_pad of this screen, or none here.
        elif draw_pad_feature.is_value_call(node):
            _pad = self._get_comp_from_py_var(node.func.value.id)
            return draw_pad_feature.value_java(
                node, _pad.get('_java_var') if _pad and _pad.get('comp_type') == draw_pad_feature.COMPONENT
                else None, self._val_to_java)
        # flashlight.is_on() / available() — o estado real da luz, que
        # qualquer coisa no telemóvel pode ter mudado.
        elif flashlight_feature.is_value_call(node):
            return flashlight_feature.value_java(node)
        elif wallpaper_feature.is_value_call(node):
            return wallpaper_feature.value_java(node)
        elif camera_feature.is_value_call(node):
            return camera_feature.value_java(node)
        # sensors.available() / battery.level/charging/saver()
        elif sensors_feature.is_value_call(node):
            return sensors_feature.value_java(node)
        # crash.last() -- o relatorio da execucao anterior, ou vazio.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr == 'last'
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'crash'):
            return 'ApkpyCrashHandler.last(getApplicationContext())'
        # language.get() -- a escolha guardada, senao a lingua do aparelho.
        # E a mesma ordem do Previewer, que e o que faz os dois concordarem.
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute)
              and node.func.attr in ('get', 'available')
              and isinstance(node.func.value, ast.Name)
              and node.func.value.id == 'language'):
            if node.func.attr == 'available':
                _tags = [_I18N[0]['default']] + sorted(
                    tag for tag in _I18N[0]['table'] if tag != _I18N[0]['default'])
                return '"%s"' % _escape_java_literal(
                    json.dumps([tag for tag in _tags if tag]))
            return ('_apkpyStorageGet("__apkpy_language", '
                    'java.util.Locale.getDefault().toLanguageTag())')
        # d.get(k, padrao), d.keys(), d.values(), d.items(), x.copy(): after
        # storage.get(), state.get() and the rest, which are the app's calls.
        elif _dict_method_java(node, self._val_to_java) is not None:
            return _dict_method_java(node, self._val_to_java)
        elif _text_method_java(node, self._val_to_java) is not None:
            return _text_method_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'format' and isinstance(node.func.value, ast.Constant) \
                and isinstance(node.func.value.value, str) \
                and _str_format_java(node, self._val_to_java) is not None:
            return _str_format_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'format' and 1 <= len(node.args) <= 2 and not node.keywords:
            # format(x, spec): the f-string's {x:spec}.
            _spec = node.args[1] if len(node.args) > 1 else ast.Constant(value='')
            if isinstance(_spec, ast.Constant):
                _spec = ast.JoinedStr(values=[_spec] if _spec.value else [])
            else:
                _spec = ast.JoinedStr(values=[ast.FormattedValue(value=_spec, conversion=-1, format_spec=None)])
            return _formatted_java(self._val_to_java(node.args[0]), _format_kind(node.args[0], self._val_to_java),
                                   _spec, -1, node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'chr' and len(node.args) == 1:
            return "_apkpyChr(Long.parseLong(String.valueOf(%s).trim()))" % self._val_to_java(node.args[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'ord' and len(node.args) == 1:
            return "String.valueOf(_apkpyOrd(String.valueOf(%s)))" % self._val_to_java(node.args[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'split':
            # Uma lista, que aqui e texto JSON. O String[] do Java nao era:
            # String.valueOf dele e um endereco, e um for sobre isso nao corria.
            return _split_java(node, self._val_to_java)

        # Métodos de string: .upper()/.lower()/.strip()/.replace(a, b)
        # (devolvem String → encaixam no modelo "tudo é String")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
                'upper', 'lower', 'strip', 'replace', 'title', 'find',
                'count', 'join', 'startswith', 'endswith'):
            base = self._val_to_java(node.func.value)
            m = node.func.attr
            _a0 = (f"String.valueOf({self._val_to_java(node.args[0])})"
                   if node.args else '""')
            if m == 'title':
                return f"_apkpyTitle(String.valueOf({base}))"
            if m == 'find':
                return f"String.valueOf(String.valueOf({base}).indexOf({_a0}))"
            if m == 'count':
                if _kind_from(self._val_to_java, node.func.value) == 'list':
                    return f"_apkpyListCount(String.valueOf({base}), {_a0})"
                return f"_apkpyCount(String.valueOf({base}), {_a0})"
            if m == 'join':
                if node.args and _kind_from(self._val_to_java, node.args[0]) == 'dict':
                    # A dict gives its keys, as in Python; its JSON text
                    # was joined letter by letter.
                    _a0 = f"_apkpyKeys(String.valueOf({self._val_to_java(node.args[0])})).toString()"
                return f"_apkpyJoin(String.valueOf({base}), {_a0})"
            if m in ('startswith', 'endswith'):
                # str(True) em Python e "True", com maiuscula; o
                # String.valueOf(boolean) do Java da "true". Mostrar um ao
                # lado do outro seria divergencia visivel numa etiqueta.
                return f'_apkpyBool({_affix_java(node, base, self._val_to_java)})'
            if m == 'upper':
                # Locale.ROOT: sem ele um telemovel turco transforma "I" num
                # i sem ponto e deixa de bater certo com o Python.
                return f"String.valueOf({base}).toUpperCase(java.util.Locale.ROOT)"
            if m == 'lower':
                return f"String.valueOf({base}).toLowerCase(java.util.Locale.ROOT)"
            if m == 'strip':
                return f"String.valueOf({base}).trim()"
            a = self._val_to_java(node.args[0]) if node.args else '""'
            b = self._val_to_java(node.args[1]) if len(node.args) > 1 else '""'
            return f"String.valueOf({base}).replace(String.valueOf({a}), String.valueOf({b}))"

        # len(x): nº de itens se x for lista/JSON, senão nº de caracteres.
        # Devolvido como String (modelo "tudo é String"); _apkpyLen decide em runtime.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'len':
            return _len_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == unpacking_feature.UNPACK:
            return _unpack_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == item_feature.LISTOP:
            return _listop_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in ('sorted', 'reversed') and len(node.args) == 1 \
                and not isinstance(node.args[0], ast.Starred):
            return _sorted_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'index' and len(node.args) == 1 and not node.keywords:
            # lista.index(x) or texto.index(sub): where it is, or the ValueError.
            _ik = 3 if _kind_from(self._val_to_java, node.func.value) == 'text' else 0
            return "_apkpyIndexOf(String.valueOf(%s), %s, %d)" % (
                self._val_to_java(node.func.value), _json_value_java(node.args[0], self._val_to_java), _ik)
        elif isinstance(node, (ast.Compare, ast.BoolOp)) or (
                isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)):
            return _logic_value_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == item_feature.SETITEM:
            return _setitem_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == item_feature.DELITEM:
            return _delitem_java(node, self._val_to_java)
        # list(x) — em Python isto tira uma copia para quem recebe nao ficar
        # com a mesma lista. Aqui o valor E texto JSON, que ja e imutavel: a
        # copia acontece por si, e a traducao honesta e o proprio valor.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name)                 and node.func.id == 'list':
            return _list_call_java(node, self._val_to_java)

        # json_get(json_str, "dot.path") → _jsonGet(json_str, "dot.path")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'json_get':
            json_arg = self._val_to_java(node.args[0]) if node.args else '""'
            path_arg = self._val_to_java(node.args[1]) if len(node.args) > 1 else '""'
            return f"_jsonGet(String.valueOf({json_arg}), {path_arg})"

        # random.randint(a, b) / random.choice(lista) / random.random()
        # (o preview corre o random real do Python; no Android usa java.util.Random
        # — os valores NÃO coincidem entre os dois, e está certo: é aleatório.)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'random':
            _rattr = node.func.attr
            if _rattr == 'randint' and len(node.args) >= 2:
                _ra = self._val_to_java(node.args[0]); _rb = self._val_to_java(node.args[1])
                return f"_apkpyRandInt(String.valueOf({_ra}), String.valueOf({_rb}))"
            if _rattr == 'choice' and node.args:
                _rl = self._val_to_java(node.args[0])
                return f"_apkpyChoice(String.valueOf({_rl}))"
            if _rattr == 'random':
                return "String.valueOf(Math.random())"

        # datetime.now()/date()/time()/year()/month()/day()/hour()/minute()/second()
        # (o preview corre o datetime real do Python; no Android usa SimpleDateFormat
        # — o formato coincide, os valores ao milissegundo não, igual ao random.)
        elif _datetime_call_to_java(node) is not None:
            return _datetime_call_to_java(node)

        # files.path("nome") → caminho absoluto do ficheiro local (offline).
        # Usado inline, ex.: audio.play(files.path("song.mp3")).
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'files' \
                and node.func.attr == 'path':
            _name = self._val_to_java(node.args[0]) if node.args else '""'
            return f"(new java.io.File(getApplicationContext().getFilesDir(), String.valueOf({_name})).getAbsolutePath())"

        # auth.token() → o access token OAuth guardado (ou "" se não logado). Usa-se
        # inline, ex.: https.get(url, headers={"Authorization": "Bearer " + auth.token()}).
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
                and node.func.attr == 'token':
            # Renewed in the background a few minutes before it expires.
            return 'ApkpyAuth.token(getApplicationContext())'
        # auth.claims() -> the id_token's payload, as a JSON object.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
                and node.func.attr == 'claims':
            return 'ApkpyAuth.claims(getApplicationContext())'
        # auth.is_logged_in() as a value, not only in an if.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'auth' \
                and node.func.attr == 'is_logged_in':
            return '(ApkpyAuth.loggedIn(getApplicationContext()) ? ApkpyValues.TRUE : ApkpyValues.FALSE)'

        # crypto.hash_password(pw, algo="sha256", iterations=200000) →
        # _apkpyHashPassword(...). Funciona em qualquer expressão (storage.set,
        # db.execute, atribuições, f-strings) porque todas passam por _val_to_java.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr == 'hash_password':
            pw_arg = self._val_to_java(node.args[0]) if node.args else '""'
            algo, iters = 'sha256', 200000
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                algo = str(node.args[1].value).lower()
            if len(node.args) > 2 and isinstance(node.args[2], ast.Constant):
                iters = int(node.args[2].value)
            for kw in node.keywords:
                if kw.arg == 'algo' and isinstance(kw.value, ast.Constant):
                    algo = str(kw.value.value).lower()
                elif kw.arg == 'iterations' and isinstance(kw.value, ast.Constant):
                    iters = int(kw.value.value)
            algo = 'sha512' if algo == 'sha512' else 'sha256'
            iters = max(1, iters)
            return f'_apkpyHashPassword(String.valueOf({pw_arg}), "{algo}", {iters})'

        # crypto.encrypt(t) / crypto.decrypt(t) → AES-256-GCM + Android Keystore
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr in ('encrypt', 'decrypt'):
            arg = self._val_to_java(node.args[0]) if node.args else '""'
            # password= changes the key AND the format: the result becomes a
            # standard AES-GCM box that travels, instead of one only this
            # phone's Keystore can open.
            pw_node = None
            for _kw in node.keywords:
                if _kw.arg == 'password':
                    pw_node = _kw.value
            if pw_node is None and len(node.args) > 1:
                pw_node = node.args[1]
            if pw_node is not None:
                pw = self._val_to_java(pw_node)
                helper = ('_apkpyEncryptPw' if node.func.attr == 'encrypt'
                          else '_apkpyDecryptPw')
                return (f'{helper}(String.valueOf({arg}), '
                        f'String.valueOf({pw}))')
            helper = '_apkpyEncrypt' if node.func.attr == 'encrypt' else '_apkpyDecrypt'
            return f'{helper}(String.valueOf({arg}))'

        # crypto.token(n) -> n bytes de SecureRandom em hex. Existe porque
        # quem precisa de um id de sessao alcanca o `random`, que e' previsivel.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr == 'token':
            count = 16
            if node.args and isinstance(node.args[0], ast.Constant):
                try:
                    count = max(1, min(64, int(node.args[0].value)))
                except (TypeError, ValueError):
                    count = 16
            return f'_apkpyToken({count})'

        # crypto.totp(secret) -> os digitos de um autenticador. Sem rede,
        # sem conta: HMAC-SHA1 sobre o relogio, como manda o RFC 6238.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr == 'totp':
            secret = self._val_to_java(node.args[0]) if node.args else '""'
            digits, period = 6, 30
            for _kw in node.keywords:
                if _kw.arg in ('digits', 'period') and isinstance(_kw.value, ast.Constant):
                    try:
                        if _kw.arg == 'digits':
                            digits = max(6, min(8, int(_kw.value.value)))
                        else:
                            period = max(1, int(_kw.value.value))
                    except (TypeError, ValueError):
                        pass
            return f'_apkpyTotp(String.valueOf({secret}), {digits}, {period})'

        # crypto.hash(t) / crypto.hash_file(p) -> SHA-256 em hex. Integridade
        # e comparacao; palavras-passe continuam no hash_password.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'crypto' \
                and node.func.attr in ('hash', 'hash_file'):
            arg = self._val_to_java(node.args[0]) if node.args else '""'
            helper = '_apkpySha256' if node.func.attr == 'hash' else '_apkpySha256File'
            return f'{helper}(String.valueOf({arg}))'

        # db.last_insert_id() → rowid do último INSERT (devolvido como String,
        # encaixa no modelo "tudo é String"; funciona em f-strings e params ?)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'db' \
                and node.func.attr == 'last_insert_id':
            return '_dbLastInsertId()'

        # db.query(sql) / db.query(sql, [params]) usado INLINE numa expressão
        # (ex.: for row in db.query(...)). Devolve a String JSON, tal como o
        # Previewer — sem isto, iterar a query diretamente dava "" (0 linhas).
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'db' \
                and node.func.attr == 'query':
            sql_arg = self._val_to_java(node.args[0]) if node.args else '""'
            params_node = node.args[1] if len(node.args) > 1 else None
            if params_node is None:
                for kw in node.keywords:
                    if kw.arg == 'params':
                        params_node = kw.value
            _qp = _sql_params_java(params_node, self._val_to_java)
            return f"_sqliteQuery(String.valueOf({sql_arg}), {_qp})" if _qp else f"_sqliteQuery(String.valueOf({sql_arg}))"

        # int(x) → faz parsing numérico (devolvido como String para encaixar no
        # modelo "tudo é String" do resto do código gerado)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'int':
            return f"String.valueOf({_int_call_java(node, self._numeric_java_expr, self._val_to_java)})"

        # float(x) → parsing numérico decimal (String, como o int())
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'float':
            # _apkpyFloat: float("12345678") is 12345678.0 in Python and
            # was 1.2345678E7 here.
            return f"_apkpyFloat({_float_call_java(node, self._numeric_java_expr, self._val_to_java)})"

        # str(x) → String.valueOf(x)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'str':
            if node.args and isinstance(node.args[0], ast.Constant) \
                    and (node.args[0].value is None or isinstance(node.args[0].value, bool)):
                return '"%s"' % node.args[0].value      # str(False) is "False", not "false"
            inner = self._val_to_java(node.args[0]) if node.args else '""'
            if node.args and tuples_feature.is_tuple(node.args[0]):
                # str((1, 2)) is (1, 2), and str((1,)) is (1,).
                return f"_apkpyShowTuple(String.valueOf({inner}))"
            if node.args and tuples_feature.holds_tuples(node.args[0]):
                # str(c.most_common(2)) is [('tea', 2), ('jam', 1)].
                return f"_apkpyShowTuples(String.valueOf({inner}))"
            if node.args and _kind_from(self._val_to_java, node.args[0]) in ('list', 'dict'):
                # str([1, "a", None]) is [1, 'a', None], not the JSON it is kept as.
                return f"_apkpyShow(String.valueOf({inner}))"
            # str(flag) is the text "True", not the True of the app: in a
            # list it went in as JSON true and came out "true". Only what can
            # hold one of them is wrapped: text written out, a sum, an
            # f-string are text already.
            text = (f"ApkpyValues.text(String.valueOf({inner}))"
                    if node.args and _may_be_singleton(node.args[0])
                    else f"String.valueOf({inner})")
            # str(d["a"]) of {"a": ["tea"]}: ['tea'], not the JSON ["tea"].
            raw = _shown_raw_java(node.args[0], text, self._val_to_java) if node.args else None
            return raw or text
        # isinstance(x, T): True / False of the app.
        elif _is_isinstance(node):
            return f"({_isinstance_java(node, self._val_to_java)} ? ApkpyValues.TRUE : ApkpyValues.FALSE)"
        # bool(x): Python's truth of x, as the True / False of the app.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'bool' \
                and len(node.args) <= 1 and not node.keywords:
            if not node.args:
                return "ApkpyValues.FALSE"
            return f"({_truthy_java(node.args[0], self._val_to_java)} ? ApkpyValues.TRUE : ApkpyValues.FALSE)"

        # t("chave") dentro de uma funcao: em runtime e o getString que
        # escolhe a lingua, exactamente como o layout faz com @string/.
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 't' and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)):
            _key = node.args[0].value
            _check_translation_key(_key, node)
            return "getString(R.string.%s)" % i18n_feature.resource_name(_key)

        # math.sqrt(x) / math.pi -> java.lang.Math, 1 para 1 (ver _MATH_CALLS).
        elif (isinstance(node, (ast.Call, ast.Attribute))
                and _math_java(node, self._val_to_java) is not None):
            return "String.valueOf(%s)" % _math_java(node, self._val_to_java)
        elif _json_call(node) is not None and _json_module_java(node, self._val_to_java) is not None:
            # json.loads(text) / json.dumps(value, ...): features/json_module.py
            return _json_module_java(node, self._val_to_java)

        # pow(a, b, m): a whole number, exact (see _numeric_call_java).
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'pow' and len(node.args) == 3 and not node.keywords:
            _pm = _numeric_call_java(node, self._numeric_java_expr, self._val_to_java)
            if _pm is None:
                unsupported.raise_unsupported(
                    node,
                    cause=('pow() with a modulus works on whole numbers, and ApkPy '
                           'cannot tell that these are.'),
                    suggestions=['Say which kind of number each one is: '
                                 'pow(int(a), int(b), 7).'],
                )
            return f"String.valueOf({_pm[0]})"

        # min/max(items, key=...): the keys came from features/sort_key.py.
        elif _has_sort_keys(node):
            return _extreme_by_java(node, self._val_to_java)
        # abs / min / max / sum. Passam por helpers em vez de irem diretos ao
        # Math porque o Python distingue inteiro de decimal (abs(-3) e 3, nao
        # 3.0) e aqui todos os valores sao texto -- so um helper pode manter
        # essa diferenca.
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in ('abs', 'min', 'max', 'sum')
                and node.args and not node.keywords):
            _bn = node.func.id
            if _bn == 'abs' and len(node.args) == 1:
                return "_apkpyAbs(String.valueOf(%s))" % self._val_to_java(node.args[0])
            if _bn == 'sum' and len(node.args) == 1:
                return "_apkpySum(String.valueOf(%s))" % self._val_to_java(node.args[0])
            if _bn in ('min', 'max'):
                _vals = ", ".join("String.valueOf(%s)" % self._val_to_java(a)
                                  for a in node.args)
                return "_apkpyExtreme(%s, %s)" % (
                    'true' if _bn == 'max' else 'false', _vals)
            unsupported.raise_unsupported(node)

        # round(x) -> inteiro mais próximo ; round(x, n) -> n casas decimais.
        #
        # Math.rint e nao Math.round. O Python arredonda o meio para o PAR
        # (round(2.5) == 2) e o Math.round manda sempre para cima, por isso
        # round(2.5) dava 2 no Previewer e 3 no telemovel, sem uma palavra.
        # Estava aqui escrito que era "irrelevante para dinheiro vindo de uma
        # divisao" — e' o contrario: dividir uma conta ao meio e' o caminho
        # mais curto para um .5 exato. O Math.rint tem a regra do Python.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'round':
            # round(x) devolve um int em Python, e round(um int, n) tambem.
            return _round_java(node, self._val_to_java, self._numeric_java_expr)

        # f-strings: f"...{var}..." → "..." + String.valueOf(var) + "..."
        # (suporta format spec :.Nf p/ casas decimais; ver _fstring_node_to_java)
        elif isinstance(node, ast.JoinedStr):
            return _fstring_node_to_java(node, self._val_to_java)
        # aritmética numérica:  int(x) * int(y),  float(a) / int(b),  c - 1 ...
        # Operandos têm de ser numéricos (int()/float()/literais). Se não forem,
        # o '+' vira concatenação de strings; os outros operadores não se aplicam
        # a strings (devolvem "" — erro silencioso, igual ao resto do modelo).
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            # "%.2f" % x: text formatting, not the remainder of a division.
            return _percent_java(node, self._val_to_java)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, _ARITH_OPS):
            _ne = self._numeric_java_expr(node)
            if _ne is not None:
                # O sinalizador is_float diz quando o resultado e um decimal:
                # so ai a apresentacao do Java diverge da do Python.
                if _ne[1]:
                    return f"_apkpyFloat({_ne[0]})"
                return f"String.valueOf({_ne[0]})"
            if isinstance(node.op, ast.Add):
                return _add_java(node, self._val_to_java, self._numeric_java_expr)
            if _repeat_java(node, self._val_to_java, self._numeric_java_expr) is not None:
                return _repeat_java(node, self._val_to_java, self._numeric_java_expr)
            if unsupported.reaches_other_runtime(node):
                # job.attempt() e vazio na copia da Activity, e de proposito.
                return '""'
            # item["price"] * item["qty"]: decidido quando a app corre.
            _rt = _arith_any_java(node, self._val_to_java)
            if _rt is not None:
                return _rt
            # Uma conta sem traducao voltava como "": o Previewer calculava e o
            # telemovel mostrava nada, sem uma palavra no build.
            unsupported.raise_untranslated_arithmetic(node, _typed_operand(node, self._val_to_java))
        # screen.get_param("key") / screen.get_param("key", "default")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get_param':
            key = node.args[0].value if node.args and isinstance(node.args[0], ast.Constant) else None
            default_node = node.args[1] if len(node.args) > 1 else None
            if key:
                if default_node:
                    default_val = self._val_to_java(default_node)
                    return f'(getIntent().getStringExtra("{key}") != null ? getIntent().getStringExtra("{key}") : {default_val})'
                return f'getIntent().getStringExtra("{key}")'
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'get_value':
            py_var = node.func.value.id if isinstance(node.func.value, ast.Name) else None
            jv = self._get_jv_from_py_var(py_var)
            comp_dict = next((cc for cc in self.all_comps_flat if cc.get('_py_var') == py_var), None)
            if jv and comp_dict:
                ctype = comp_dict.get('comp_type', '')
                itype = comp_dict.get('input_type', 'text') if ctype in ('inputs', 'input_field') else ''
                if ctype in choice_feature.COMPONENTS:
                    return "(%s)" % choice_feature.get_java(jv)
                if itype == 'radio':
                    return f"(((android.widget.RadioGroup)findViewById(R.id.{jv}Group)).getCheckedRadioButtonId() != -1 ? ((android.widget.RadioButton)findViewById(((android.widget.RadioGroup)findViewById(R.id.{jv}Group)).getCheckedRadioButtonId())).getText().toString() : \"\")"
                elif itype == 'switch':
                    return f"(((androidx.appcompat.widget.SwitchCompat)findViewById(R.id.{jv})).isChecked() ? \"true\" : \"false\")"
                elif itype == 'checkbox':
                    return f"(((android.widget.CheckBox)findViewById(R.id.{jv})).isChecked() ? \"true\" : \"false\")"
                elif itype == 'select':
                    return f"(((android.widget.Spinner)findViewById(R.id.{jv})).getSelectedItem() != null ? ((android.widget.Spinner)findViewById(R.id.{jv})).getSelectedItem().toString() : \"\")"
                elif itype == 'range':
                    return f"(String.valueOf(((android.widget.SeekBar)findViewById(R.id.{jv})).getProgress()))"
                elif itype in ('text', 'password', 'search', 'textarea', 'number'):
                    return f"(((android.widget.EditText)findViewById(R.id.{jv})).getText().toString())"
                else:
                    return f"(((android.widget.TextView)findViewById(R.id.{jv})).getText().toString())"
            # O componente não está NESTE ecrã. O mesmo callback é escrito em
            # todas as Activities, e onde o campo não existe o vazio é a
            # resposta certa — get_value é traduzível, só não aqui. Sem este
            # return caía na guarda lá em baixo e acusava Python por traduzir.
            _ELSEWHERE_EMPTY[0].add(id(node))
            return '""'
        # Chamada a função do utilizador que devolve valor: y = f(a)
        # native.java("x") -- o Java da propria app, usado como valor.
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and native_feature.function_for(node.func.id) is not None:
            return native_feature.value_call_java(node, self._val_to_java)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in self.functions_map:
            _fargs = _callback_call_args(node.func.id, node.args, self._val_to_java, self.functions_map, self.boolean_first_arg_callbacks, self._cur_bool_args[0])
            return f"pythonCallback_{node.func.id}({_fargs})"
        # Nada abaixo soube traduzir isto. Devolver '""' aqui era o erro
        # silencioso mais caro do gerador: a app compilava e mostrava um vazio.
        unsupported.check_value(node)
        return '""'

    def _kind_of(self, node):
        """What *node* holds, read from the source: see _static_kind."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == 'get_value' and isinstance(node.func.value, ast.Name):
            comp = next((cc for cc in self.all_comps_flat
                         if cc.get('_py_var') == node.func.value.id), None)
            if comp is None:
                return None
            # chips(multiple=True) answers with a list; every other
            # component with text.
            if comp.get('comp_type') in choice_feature.COMPONENTS and comp.get('multiple'):
                return 'list'
            return 'text'
        return _static_kind(node, self._struct_kinds)

    def _dict_node_to_java(self, node, var_name, indent):
        """Converte um ast.Dict Python num bloco Java de inicialização de HashMap."""
        result = []
        result.append(f"{indent}java.util.Map<String, String> {var_name} = new java.util.HashMap<>();")
        if isinstance(node, ast.Dict):
            for k_node, v_node in zip(node.keys, node.values):
                k = self._val_to_java(k_node)
                v = self._val_to_java(v_node)
                result.append(f"{indent}{var_name}.put({k}, {v});")
        return result
