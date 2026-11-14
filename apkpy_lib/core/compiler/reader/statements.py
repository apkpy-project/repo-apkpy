"""The lines of a function of the app, each as a command."""
import ast

from ...features import data as data_feature
from ... import unsupported
from ..state import _GLOBALS
from ..expressions import _CMP_OPS, _cond_shape_supported, _written_comparand
from ..statements import _LOOKUP_CATCHERS, _except_types, _raise_command, _stamp_commands
from ..prescan import _queue_global_write
from ..manifest import _permission_symbol


class StatementReader:
    """The lines of a function of the app, each as a command."""

    # ── Visitors ──────────────────────────────────────────────────────────────

    def _parse_statements(self, statements):
        cmds = []
        # Cada comando fica com a linha de onde veio, para que uma recusa na
        # fase de geracao (ex.: o Worker de um job) aponte o writehere.py e nao
        # o compiler.py. Carimba-se o lote da instrucao anterior no inicio de
        # cada volta, por isso um `continue` num ramo nao o salta.
        _stamped = [0]
        _previous = [None]
        for stmt in statements:
            _queue_global_write(cmds, _stamped[0], _previous[0])
            _stamp_commands(cmds, _stamped, _previous[0])
            _previous[0] = stmt
            # ── Expressões simples (chamadas standalone) ──────────────────────
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                self._call_statement(cmds, stmt)

            # ── Atribuições (val = storage.get(...) ou val = comp.get_value()) ─
            elif isinstance(stmt, ast.Assign):
                self._assign_statement(cmds, stmt)

            # ── Atribuição aumentada: x += v / -= / *= / /= / %= ──────────────
            # Desugar para `x = x <op> v` e reaproveitar o local_string_assign
            # (aritmética numérica OU concatenação de strings, conforme o tipo).
            elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                _synth = ast.BinOp(
                    left=ast.Name(id=stmt.target.id, ctx=ast.Load()),
                    op=stmt.op,
                    right=stmt.value,
                )
                cmds.append({'type': 'local_string_assign',
                             'var': stmt.target.id, 'val_node': _synth})

            # ── Condicionais ──────────────────────────────────────────────────
            elif isinstance(stmt, ast.If):
                self._if_statement(cmds, stmt)

            # ── Loops for ─────────────────────────────────────────────────────
            # for x in ["a", "b"]:  |  for i in range(n):  |  for row in rows:
            # (rows = JSON de db.query / resposta https — itera as linhas)
            elif isinstance(stmt, ast.For):
                # A dict or a text written out is walked like one in a name
                # (keys, letters); a set has no order to walk in.
                if not isinstance(stmt.target, ast.Name) or stmt.orelse \
                        or isinstance(stmt.iter, ast.Set):
                    # Cada um destes deixava o loop de fora, ou corria-o sobre
                    # nada no telemovel enquanto o Previewer o corria.
                    unsupported.raise_untranslated_loop(stmt)
                if isinstance(stmt.target, ast.Name):
                    cmds.append({
                        'type': 'for_loop',
                        'var': stmt.target.id,
                        'iter_node': stmt.iter,
                        'body': self._parse_statements(stmt.body),
                        'body_ast': stmt.body,
                    })

            # ── Loop while ────────────────────────────────────────────────────
            # while <cond>:  — a condição reutiliza as formas suportadas nos `if`
            # (comparações, and/or/not, nome, bool). Formas não suportadas são
            # ignoradas (como nos `if`), em vez de gerar Java errado.
            elif isinstance(stmt, ast.While) and _cond_shape_supported(stmt.test):
                if stmt.orelse:
                    # Rewritten as a flag inside a function (features/
                    # loop_else.py); anywhere else the else was left out.
                    unsupported.raise_untranslated_loop(stmt)
                cmds.append({
                    'type': 'while_loop',
                    'test': stmt.test,
                    'body': self._parse_statements(stmt.body),
                })

            # ── break / continue ──────────────────────────────────────────────
            # Só aparecem dentro de loops (o Python já garante isso ao fazer
            # parse — `break` fora de loop é SyntaxError). Mapeiam direto para
            # o break/continue do for nativo em Java.
            elif isinstance(stmt, ast.Break):
                cmds.append({'type': 'break'})
            elif isinstance(stmt, ast.Continue):
                cmds.append({'type': 'continue'})
            elif isinstance(stmt, ast.Return):
                cmds.append({'type': 'return', 'value_node': stmt.value})

            # ── raise ─────────────────────────────────────────────────────────
            # Python's built-in errors by name (ApkpyValues.Raised); a bare
            # raise, or raise e, inside an except throws the caught one again.
            elif isinstance(stmt, ast.Raise):
                cmds.append(_raise_command(stmt, getattr(self, '_except_stack', [])))

            # ── try / except / finally ────────────────────────────────────────
            # Each except keeps its Python types, tested on the phone by
            # ApkpyValues.isA (see _emit_try_block). The else of a try was
            # rewritten before this (features/errors.py).
            elif isinstance(stmt, ast.Try):
                self._try_statement(cmds, stmt)

            # Uma instrução que ninguém acima reconheceu era deitada fora em
            # silêncio: o corpo da função ficava sem ela e ninguém sabia.
            else:
                unsupported.check_statement(stmt)
        _queue_global_write(cmds, _stamped[0], _previous[0])
        _stamp_commands(cmds, _stamped, _previous[0])
        return cmds

    def _assign_statement(self, cmds, stmt):
        """name = value, name = a call, and the other things an assignment can be."""
        target = stmt.targets[0] if stmt.targets else None
        val    = stmt.value
        target_name = target.id if isinstance(target, ast.Name) else None
        _assign_before = len(cmds)
        if len(stmt.targets) != 1 or target_name is None:
            # a, b = ... / row["k"] = ... / obj.attr = ... saiam daqui
            # sem gerar linha nenhuma, e sem uma palavra.
            unsupported.raise_untranslated_assignment(stmt)

        data_tx_assign = (
            data_feature.parse_tx_command(self, val, assign_to=target_name)
            if target_name and isinstance(val, ast.Call) else None
        )

        if data_tx_assign is not None:
            cmds.append(data_tx_assign)

        elif target_name and isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute) and val.func.attr == 'get' and isinstance(val.func.value, ast.Name) and val.func.value.id == 'storage':
            key = val.args[0].value if val.args and hasattr(val.args[0], 'value') else ''
            default_node = val.args[1] if len(val.args) > 1 else None
            default_kw   = self._kw(val.keywords, 'default')
            if default_node is not None and hasattr(default_node, 'value'):
                v = default_node.value
                default_val = ('"true"' if v else '"false"') if isinstance(v, bool) else str(v)
            elif default_kw is not None:
                default_val = str(default_kw)
            else:
                default_val = '""'
            if not default_val.startswith('"'):
                default_val = f'"{default_val}"'
            cmds.append({'type': 'storage_get_assign', 'var': target_name,
                         'key': key, 'default': default_val,
                         'key_node': val.args[0] if val.args else None,
                         'default_node': default_node if default_node is not None
                         else self._kw_node(val.keywords, 'default')})

        # val = db.query(sql) / db.query(sql, [a, b]) / db.query(sql, params=[a, b])
        elif target_name and isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute) and val.func.attr == 'query' and isinstance(val.func.value, ast.Name) and val.func.value.id == 'db':
            if val.args:
                sql_node = val.args[0]
                params_node = val.args[1] if len(val.args) > 1 else self._kw_node(val.keywords, 'params')
                cmds.append({'type': 'db_query_assign', 'var': target_name, 'sql_node': sql_node, 'params_node': params_node})

        # ok = crypto.verify_password(pw, stored) — tem de gerar um
        # boolean Java a sério (uma String "false" seria truthy no
        # modelo `if (var != null && !var.isEmpty())`).
        elif target_name and isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute) and val.func.attr == 'verify_password' and isinstance(val.func.value, ast.Name) and val.func.value.id == 'crypto':
            if len(val.args) >= 2:
                cmds.append({'type': 'crypto_verify_assign', 'var': target_name,
                             'pw_node': val.args[0], 'stored_node': val.args[1]})

        # val = comp.get_value()
        elif target_name and isinstance(val, ast.Call) and isinstance(val.func, ast.Attribute) and val.func.attr == 'get_value':
            py_var = val.func.value.id if isinstance(val.func.value, ast.Name) else None
            if py_var:
                cmds.append({'type': 'comp_get_value_assign',
                             'var': target_name, 'py_var': py_var})

        elif target_name and (isinstance(val, (ast.JoinedStr, ast.Constant, ast.BinOp, ast.Name, ast.Subscript, ast.Call, ast.List, ast.Tuple, ast.Dict, ast.IfExp, ast.Attribute, ast.Compare, ast.BoolOp))
                              or (isinstance(val, ast.UnaryOp) and isinstance(val.op, (ast.USub, ast.UAdd, ast.Not)))):
            # IfExp, Attribute (math.pi) e -x ja tinham traducao no
            # _val_to_java; faltava so deixa-los chegar la.
            # Atribuição de string local: url = f"...", msg = "...", etc.
            # (listas e dicts viram JSON em Java — iteráveis com
            # `for x in xs:`, e prontos a servir de corpo de um pedido.
            # Um `body = {...}` não estava nesta lista: não gerava linha
            # nenhuma, e o Java ficava a usar um nome nunca declarado.)
            cmds.append({'type': 'local_string_assign', 'var': target_name, 'val_node': val})

        if len(cmds) == _assign_before:
            # Nada acima tomou este valor. A linha saia da app, e o
            # nome ficava por declarar para quem o lesse a seguir.
            unsupported.raise_untranslated_assignment(stmt)

    def _if_statement(self, cmds, stmt):
        """if: a permission, a name, a comparison, or a condition written whole."""
        test = stmt.test
        _if_before = len(cmds)
        if isinstance(test, ast.Call) and getattr(test.func, 'attr', '') == 'has':
            perm = test.args[0].value if test.args and hasattr(test.args[0], 'value') else ""
            perm = _permission_symbol(str(perm).strip())
            cmds.append({
                'type': 'if_has_permission',
                'perm': perm,
                'true_body': self._parse_statements(stmt.body),
                'false_body': self._parse_statements(stmt.orelse)
            })
        elif isinstance(test, ast.Name):
            cmds.append({
                'type': 'if_var',
                'var': test.id,
                'true_body': self._parse_statements(stmt.body),
                'false_body': self._parse_statements(stmt.orelse)
            })
        elif isinstance(test, ast.Compare):
            # A `global` name is read from the shared store, which
            # if_compare's bare name would skip: it goes as a node.
            left = test.left.id if isinstance(test.left, ast.Name) \
                and test.left.id not in _GLOBALS[0] else ""
            if len(test.ops) > 1 and _cond_shape_supported(test):
                cmds.append({
                    'type': 'if_cond',
                    'test': test,
                    'true_body': self._parse_statements(stmt.body),
                    'false_body': self._parse_statements(stmt.orelse),
                })
            elif len(test.ops) == 1 and test.comparators:
                op_node = test.ops[0]
                comp_node = test.comparators[0]
                # if_compare keeps the right side as a value, so it is
                # only for one written out: text, a number, True or
                # False. `if a == b:` came through here with "" for b
                # and was built as a.equals("") -- since 1.8.0 at least.
                written = _written_comparand(comp_node)
                right = comp_node.value if written else ""

                if left == '__name__' and right == '__main__':
                    return  # Ignorar este bloco na compilação para Android

                op = _CMP_OPS.get(type(op_node))  # ==, !=, <, >, <=, >=
                if written and op is not None and (left or isinstance(test.left, (ast.Subscript, ast.Call, ast.JoinedStr, ast.Name))):
                    # left pode ser um nome simples OU uma expressão
                    # (ex.: row["name"] == "Manga" dentro de um for) —
                    # nesse caso left_node é convertido com _val_to_java.
                    cmds.append({
                        'type': 'if_compare',
                        'left': left,
                        'left_node': None if left else test.left,
                        'op': op,
                        'right': right,
                        'true_body': self._parse_statements(stmt.body),
                        'false_body': self._parse_statements(stmt.orelse)
                    })
                elif op is not None or isinstance(op_node, (ast.In, ast.NotIn, ast.Is, ast.IsNot)):
                    # `x in y`, `x not in y`, and a comparison whose left
                    # side if_compare does not take. One general path
                    # writes all of them, so they cannot drift apart.
                    cmds.append({
                        'type': 'if_cond',
                        'test': test,
                        'true_body': self._parse_statements(stmt.body),
                        'false_body': self._parse_statements(stmt.orelse),
                    })
        # if a and b:  |  if a or b:  |  if not x:  (and/or/not — Tier 1 C)
        # if a and b:  |  if not x:  |  if valor.isdigit():  (and/or/not + predicados)
        elif isinstance(test, (ast.BoolOp, ast.UnaryOp, ast.Call, ast.Constant, ast.Subscript)) and _cond_shape_supported(test):
            cmds.append({
                'type': 'if_cond',
                'test': test,
                'true_body': self._parse_statements(stmt.body),
                'false_body': self._parse_statements(stmt.orelse),
            })
        if len(cmds) == _if_before:
            # Nothing above took this condition. It used to leave the
            # whole branch out of the app without a word.
            unsupported.raise_untranslated_condition(test)

    def _try_statement(self, cmds, stmt):
        """try, with each except and its finally."""
        if stmt.orelse:
            unsupported.raise_unsupported(
                stmt,
                cause=(
                    'The else of a try runs only when nothing failed, '
                    'and its own failures are not caught. Java has no '
                    'such block.'
                ),
                suggestions=[
                    'Move the else lines below the whole try.',
                ],
                received='try ... except ... else',
            )
        c = {'type': 'try_block', 'handler': []}
        c['err'] = '_te_%d' % (id(c) & 0xFFFF)
        c['body'] = self._parse_statements(stmt.body)
        if getattr(self, '_except_stack', None) is None:
            self._except_stack = []
        for handler in stmt.handlers:
            types = _except_types(handler.type)
            self._except_stack.append((c['err'], handler.name))
            try:
                body = self._parse_statements(handler.body)
            finally:
                self._except_stack.pop()
            c['handler'].append({'type': 'except_clause', 'types': types,
                                 'name': handler.name, 'body': body})
        c['final'] = self._parse_statements(stmt.finalbody)
        c['strict'] = any(clause['types'] is None
                          or _LOOKUP_CATCHERS & set(clause['types'])
                          for clause in c['handler'])
        cmds.append(c)
