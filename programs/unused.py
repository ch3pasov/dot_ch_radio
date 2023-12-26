'''
Тут будут функции, которые (пока?) не используются
'''


def text_to_cyberhaiku(text):
    '''
    Функция, которая превращает текст в киберхайку
    '''
    lines = text.split('\n')
    max_len = max([len(line) for line in lines])
    lines_rectangled = [line+' '*(max_len-len(line)) for line in lines]
    lines_rotated = ['  '.join([line[i] for line in lines_rectangled]) for i in range(max_len)]
    cyberhaiku = ['`' + line + '`' for line in lines_rotated]
    return cyberhaiku
