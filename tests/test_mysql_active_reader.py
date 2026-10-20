import json
import unittest
from unittest.mock import patch, MagicMock
from ednna.mysql_active_reader import carregar_carteira_mysql


class ReaderTests(unittest.TestCase):
    def test_complete_snapshot(self):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(1, json.dumps({'id': 1}), '2026-10-20T09:41:00-03:00'), (2, json.dumps({'id': 2}), '2026-10-20T09:41:00-03:00')]
        context = MagicMock()
        context.__enter__.return_value = conn
        with patch('ednna.mysql_active_reader.connect', return_value=context):
            self.assertEqual(len(carregar_carteira_mysql({1, 2}, '2026-10-20T09:41:00-03:00')), 2)
            self.assertIsNone(carregar_carteira_mysql({1, 2, 3}, '2026-10-20T09:41:00-03:00'))
            self.assertIsNone(carregar_carteira_mysql({1, 2}, '2026-10-20T10:00:00-03:00'))

if __name__ == '__main__':
    unittest.main()
