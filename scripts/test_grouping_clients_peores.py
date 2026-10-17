import os
import sys
import django

sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datia.services.ai.router import IntentRouter

class DummyEmbedding:
    def search_template(self, question, threshold=0.65):
        return None

def run():
    router = IntentRouter(DummyEmbedding())
    ctx = {'empresa': 1, 'ejercicio': 2024, 'limit': 20}

    # Establecer foco inicial
    h1, d1 = router.resolve('margen clientes octubre', ctx)
    print('T1 Handler:', getattr(h1, '__name__', h1))
    print('T1 SQL:', d1.get('sql'))

    # Elíptico: peores 10
    h2, d2 = router.resolve('y los peores 10?', ctx)
    print('T2 Handler:', getattr(h2, '__name__', h2))
    print('T2 SQL:', d2.get('sql'))

    assert d2 and 'ORDER BY 2 ASC' in d2.get('sql',''), 'Orden no ASC para peores'
    assert d2 and 'LIMIT 10' in d2.get('sql',''), 'Límite no aplicado a 10'
    print('OK: peores 10 aplica ASC y LIMIT 10')

if __name__ == '__main__':
    run()
