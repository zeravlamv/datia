import os
import sys
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.ai.title_generator import TitleGenerator

tg = TitleGenerator()
state = {'empresa':1,'ejercicio':2024}

def test_case(q, expected_contains):
    title = tg.generate(q, {}, state, None)
    print(q, '=>', title)
    for token in expected_contains:
        assert token in title

test_case('¿Qué cliente ha comprado más unidades en diciembre?', ['Cliente', 'unidades', 'diciembre'])
test_case('Ranking productos top 10 septiembre 2024', ['Top 10', 'Productos', 'septiembre', '2024'])
test_case('margen clientes octubre', ['Margen', 'Cliente', 'octubre'])
test_case('peores 5 clientes por coste en marzo', ['Peores 5', 'Clientes', 'coste', 'marzo'])
test_case('ventas producto 051023 entre enero y marzo 2024', ['Ventas', 'producto', 'enero', 'marzo', '2024'])

print('OK: pruebas de generación de títulos')
