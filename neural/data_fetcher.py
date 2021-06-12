import asyncio
import os

import asyncpg

from torch_config import DB_BIND, CORPUS_DIR


async def fetch_data():
	db = await asyncpg.connect(DB_BIND)
	rs = await db.fetch('SELECT * FROM corpus WHERE truth IN (0, 1)')

	required_dirs = [
		CORPUS_DIR,
		f'{CORPUS_DIR}/raw',
		f'{CORPUS_DIR}/proc',
	]

	for dir in required_dirs:
		if not os.path.exists(dir):
			os.mkdir(dir)

	for r in rs:
		_id = r.get('id')

		label = '1' if r.get('truth') else '0'
		path = f'{CORPUS_DIR}/raw/{label}'
		if not os.path.isdir(path):
			os.mkdir(path)

		file_path = f'{path}/{_id}.txt'
		# if not os.path.isfile(file_path):
		with open(file_path, 'w', encoding='utf-8') as f:
			f.write(' '.join(r.get('data')))


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	task = loop.create_task(fetch_data())
	loop.run_until_complete(task)