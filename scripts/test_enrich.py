import os, sys, django, json
sys.path.append('C:/Users/miguel vergara/Desktop/datia')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from datia.services.ai.conversation_manager import ConversationManager

cm = ConversationManager()
cm.ensure_schema()
q1, ctx1, d1, conv1 = cm.enrich('rentabilidad productos septiembre 2024 top 20', {'empresa':1,'ejercicio':2024}, None)
print('E1:', q1)
q2, ctx2, d2, conv2 = cm.enrich('y en octubre?', {'empresa':1,'ejercicio':2024}, None)
print('E2:', q2)
print('State2:', json.dumps(ctx2.get('conversation_state')))
