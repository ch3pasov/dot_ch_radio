'''
Тут будут функции, которые (пока?) не используются
'''


# def text_to_cyberhaiku(text):
#     '''
#     Функция, которая превращает текст в киберхайку
#     '''
#     lines = text.split('\n')
#     max_len = max([len(line) for line in lines])
#     lines_rectangled = [line+' '*(max_len-len(line)) for line in lines]
#     lines_rotated = ['  '.join([line[i] for line in lines_rectangled]) for i in range(max_len)]
#     cyberhaiku = ['`' + line + '`' for line in lines_rotated]
#     return cyberhaiku


# nadezhdin_regex = r'                                <span class="progressbar__el__text">Собрано подписей: (\d+)( / 2500)?</span>'
# out = '''
# Считаю количество подписей с nadezhdin2024.ru/addresses.

# Всего собрано подписей: **{scores_all:,}**.
# С ограниченим в 2500 на регион подписей: **{scores_2500:,}**.
# Среди этих подписей нужно **100,000** идеально заполненных подписей. Сколько их сейчас — неизвестно.
# '''


# async def get_nadezhdin():
#     text = await aiohttp_get('https://nadezhdin2024.ru/addresses', 'text')
#     scores_raw = [int(region_score[0]) for region_score in re.findall(nadezhdin_regex, text)]
#     scores_all = sum(scores_raw)
#     scores_2500 = sum([min(2500, score) for score in scores_raw])
#     return out.format(scores_all=scores_all, scores_2500=scores_2500)
