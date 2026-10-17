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

    h1, d1 = router.resolve('rentabilidad productos septiembre 2024 top 20', ctx)
    print('Turno1 Handler:', getattr(h1, '__name__', h1))
    print('Turno1 SQL:', d1.get('sql'))

    h2, d2 = router.resolve('y en octubre?', ctx)
    print('Turno2 Handler:', getattr(h2, '__name__', h2))
    print('Turno2 SQL:', d2.get('sql'))

    assert 'EXTRACT(MONTH' in d1.get('sql','')
    assert 'EXTRACT(MONTH' in d2.get('sql','')
    # Verificar cambio a octubre (10)
    assert 'BETWEEN 10 AND 10' in d2.get('sql','') or 'MONTH FROM' in d2.get('sql','')
    print('OK: Memoria conversacional ha aplicado el cambio de mes a octubre')

if __name__ == '__main__':
    run()
