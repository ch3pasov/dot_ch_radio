import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp

from programs import other


ROOT = Path(__file__).resolve().parents[1]


class OpenWeatherTests(unittest.IsolatedAsyncioTestCase):
    def test_weather_module_import_does_not_require_key(self):
        environment = {**os.environ}
        environment.pop('OPENWEATHER_API_KEY', None)

        subprocess.run(
            [sys.executable, '-c', 'from programs import other'],
            check=True,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    async def test_weather_uses_environment_key_as_request_parameter(self):
        request = AsyncMock(
            return_value={
                'name': 'Берлин',
                'main': {'temp': 21, 'feels_like': 20},
                'wind': {'speed': 3},
            }
        )

        with (
            patch.dict(os.environ, {'OPENWEATHER_API_KEY': 'test-api-key'}, clear=True),
            patch.object(other, 'aiohttp_get_json', new=request),
        ):
            result = await other.get_weather(52.52, 13.405)

        request.assert_awaited_once_with(
            'https://api.openweathermap.org/data/2.5/weather',
            params={
                'lat': 52.52,
                'lon': 13.405,
                'units': 'metric',
                'lang': 'ru',
                'appid': 'test-api-key',
            },
        )
        self.assertEqual(
            result,
            'В Берлин 21℃\nОщущается как 20℃\nСкорость ветра 3м/с',
        )

    async def test_missing_key_fails_only_when_weather_is_requested(self):
        request = AsyncMock()

        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(other, 'aiohttp_get_json', new=request),
        ):
            with self.assertRaisesRegex(RuntimeError, 'не настроен'):
                await other.get_weather(52.52, 13.405)

        request.assert_not_awaited()

    async def test_weather_uses_english_provider_copy_for_fallback_locale(self):
        request = AsyncMock(
            return_value={
                'name': 'Berlin',
                'main': {'temp': 21, 'feels_like': 20},
                'wind': {'speed': 3},
            }
        )

        with (
            patch.dict(os.environ, {'OPENWEATHER_API_KEY': 'test-api-key'}, clear=True),
            patch.object(other, 'aiohttp_get_json', new=request),
        ):
            result = await other.get_weather(52.52, 13.405, locale='en')

        self.assertEqual(request.await_args.kwargs['params']['lang'], 'en')
        self.assertEqual(
            result,
            'Berlin: 21℃\nFeels like 20℃\nWind speed: 3 m/s',
        )

    async def test_client_errors_do_not_expose_request_credentials(self):
        credential_marker = 'test-api-key'
        request = AsyncMock(
            side_effect=aiohttp.ClientConnectionError(
                f'request failed with credential {credential_marker}'
            )
        )

        with (
            patch.dict(
                os.environ,
                {'OPENWEATHER_API_KEY': credential_marker},
                clear=True,
            ),
            patch.object(other, 'aiohttp_get_json', new=request),
        ):
            with self.assertRaises(RuntimeError) as caught:
                await other.get_weather(52.52, 13.405)

        self.assertNotIn(credential_marker, str(caught.exception))
        self.assertIsNone(caught.exception.__context__)

    async def test_weather_response_is_friendly_when_provider_is_unavailable(self):
        with patch.object(
            other,
            'get_weather',
            new=AsyncMock(side_effect=RuntimeError('provider unavailable')),
        ):
            result = await other.get_weather_response(52.52, 13.405)

        self.assertEqual(result, other.WEATHER_UNAVAILABLE_MESSAGE)

    def test_source_contains_no_embedded_openweather_credential(self):
        source = Path(other.__file__).read_text(encoding='utf-8')

        self.assertNotRegex(source, re.compile(r'\b[0-9a-f]{32}\b', re.IGNORECASE))
        self.assertNotIn('appid=', source)


class RuntimeSecretInjectionTests(unittest.TestCase):
    def test_template_and_compose_pass_openweather_key_by_name(self):
        template = (ROOT / 'ops' / 'telegram-api.env.tpl').read_text(encoding='utf-8')
        compose = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')

        self.assertIn(
            'OPENWEATHER_API_KEY="op://Codex Allowed/OpenWeather API/api_key"',
            template,
        )
        self.assertIn(
            'OPENWEATHER_API_KEY: "${OPENWEATHER_API_KEY:-}"',
            compose,
        )

    def test_compose_reserves_file_descriptors_for_webrtc(self):
        compose = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')

        self.assertIn('nofile:', compose)
        self.assertIn('soft: 1024', compose)
        self.assertIn('hard: 1024', compose)

    def test_direct_compose_bypass_requires_all_three_credentials(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            trace = temporary / 'trace'
            fake_docker = temporary / 'docker'
            fake_op_vault = temporary / 'op-vault'
            fake_docker.write_text(
                '#!/usr/bin/env bash\nprintf "docker\\n" >> "$TRACE_FILE"\n',
                encoding='utf-8',
            )
            fake_op_vault.write_text(
                '#!/usr/bin/env bash\nprintf "op-vault\\n" >> "$TRACE_FILE"\n',
                encoding='utf-8',
            )
            fake_docker.chmod(0o700)
            fake_op_vault.chmod(0o700)

            environment = {
                **os.environ,
                'PATH': f'{temporary}{os.pathsep}{os.environ["PATH"]}',
                'OP_VAULT_BIN': str(fake_op_vault),
                'TRACE_FILE': str(trace),
                'TELEGRAM_API_ID': 'test-id',
                'TELEGRAM_API_HASH': 'test-hash',
                'OPENWEATHER_API_KEY': 'test-weather-key',
            }
            subprocess.run(
                [ROOT / 'compose-with-secrets', 'config'],
                check=True,
                env=environment,
            )
            self.assertEqual(trace.read_text(encoding='utf-8'), 'docker\n')

            trace.unlink()
            environment.pop('OPENWEATHER_API_KEY')
            subprocess.run(
                [ROOT / 'compose-with-secrets', 'config'],
                check=True,
                env=environment,
            )
            self.assertEqual(trace.read_text(encoding='utf-8'), 'op-vault\n')


if __name__ == '__main__':
    unittest.main()
