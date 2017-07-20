from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from pathlib import Path
from tqdm import tqdm
import requests
import pprint
import os


#В зависимости от категории фестиваля у ссылки разные окончания, определяем их
def get_link_ending(category):

	categories_lions = [
		'creative-effectiveness',
		'cyber',
		'design',
		'digital-craft',
		'direct',
		'film',
		'film-craft',
		'glass-lion',
		'grand-prix-for-good',
		'integrated',
		'media',
		'mobile',
		'outdoor',
		'pr',
		'print-and-publishing',
		'product-design',
		'promo-and-activation',
		'radio',
		'titanium']

	categories_innovation = [
		'creative-data',
		'innovation']

	categories_health = [
		'grand-prix-for-good-health',
		'health-and-wellness',
		'pharma']

	categories_entertainment = [
		'entertainment',
		'entertainment-for-music']

	if category in categories_lions:
		return 'CL'
	elif category in categories_innovation:
		return 'LI'
	elif category in categories_health:
		return 'LH'
	else:
		return 'LE'

#Получаем адреса всех кейсов и информацию о них в заданной категории
def get_case_info(category, award_level_req):
	case_info = []

	category_link_ending = get_link_ending(category)

	#Загружаем эмулятор браузера
	#Страница подгружается через JavaScript, если сразу получить исходный код страницы, она будет практически пустая
	browser = webdriver.PhantomJS()
	browser.set_window_size(1024, 768)
	url = "http://player.canneslions.com/index.html#/works?category=" + category + "&festival=" + category_link_ending
	browser.get(url)
	
	#Страница грузится некоторое время, ждем пока появится элементы кейсов
	wait = WebDriverWait(browser, 10)
	element = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'c-card__wrap')))
	html = browser.page_source
	browser.quit()
	soup = BeautifulSoup(html, 'lxml')

	#Находим блоки, которые содержат ссылки на отдельные страницы кейсов
	div_list = soup.find_all('div', {"data-entry-click":True})
	
	#Из каждого блока получаем информацию о кейсе
	for div in div_list:
		
		#Получаем номер кейса, чтобы собрать ссылку
		number = div['data-entry-click']

		#Получаем название кейса, чтобы потом создать из него файл		
		case_name_dirty = soup.select('div[data-entry-click=' + number + '] h3')
		case_name = case_name_dirty[0].contents[0]
		
		#Убираем запрещенные символы из названия файла
		prohibited_chars = '<>:"/\|?*'
		for char in prohibited_chars:
			case_name = case_name.replace(char,"-")
				
		#Получаем уровень награды, если скачиваем не все
		award_level_dirty = soup.select('div[data-entry-click=' + number + '] span.c-card-level__title')
		award_level = award_level_dirty[0].contents[0]

		if award_level in award_level_req:
		
			#Поправляем лишние пробелы и убираем 'Campaign' из названия награды
			award_level = award_fix(award_level)			

			#Добавляем на вывод
			case_info.append({'number':number, 'case_name':case_name, 'award_level':award_level})

	return case_info

#Нужно для функции ниже
#https://stackoverflow.com/questions/16462177/selenium-expected-conditions-possible-to-use-or
class AnyEc:
    """ Use with WebDriverWait to combine expected_conditions
        in an OR.
    """
    def __init__(self, *args):
        self.ecs = args
    def __call__(self, driver):
        for fn in self.ecs:
            try:
                if fn(driver): return True
            except:
                pass

#Получаем ссылку на содержимое кейса по номеру и категории
def get_content_src(category, number):

	#Сложные штуки, получаем код страницы и ждем, когда загрузится JS
	browser = webdriver.PhantomJS()
	browser.set_window_size(1024, 768)
	category_link_ending = get_link_ending(category)
	url = "http://player.canneslions.com/index.html#/works?category=" + category + "&entry=" + number + "&festival=" + category_link_ending
	browser.get(url)
	
	try:
		#Ждем, пока загрузится либо картинка, либо видео, либо звук, чтобы получить ссылку на кейс
		WebDriverWait(browser, 10).until(
			AnyEc(
				EC.presence_of_element_located(
					(By.CSS_SELECTOR, 'video.media-player__video')),
				EC.presence_of_element_located(
					(By.CSS_SELECTOR, 'div.media-player img')),
				EC.presence_of_element_located(
					(By.CSS_SELECTOR, 'audio')),
			)
		)
		html = browser.page_source
		soup = BeautifulSoup(html, 'lxml')

		#Нужно понять, что это: видео, картинка или звук
		if soup.select('video.media-player__video'):
			print('Video')
			src_dirty = soup.select('video.media-player__video')
			src = src_dirty[0]['src']
		elif soup.select('div.media-player img'):
			print('Image')
			src_dirty = soup.select('div.media-player img')
			src = src_dirty[0]['src']
		elif soup.select('audio'):
			print('Audio')
			src_dirty = soup.select('audio')
			src = src_dirty[0]['src']
		else:
			print('No content')
			src = ''
	except:
		print('Loading error')
		print(url)
		#Это случай, когда нет ни картинки, ни видео
		src = ''

	browser.quit()
	return src	
		
def download_file(category, case_name, src, award):
	r = requests.get(src, stream=True)
	total_size = int(r.headers.get('content-length', 0)); 

	#Чтобы не создавать все папки вручную, используем скрипт
	directory = "./cannes/" + category + "/" + award + "/"
	if not os.path.exists(directory):
	    os.makedirs(directory)

	#Задаем параметры прогресс бару для скачки
	pbar = tqdm(
		total=total_size, unit='B', unit_scale=True, leave=True
		)

	if 'http://images-jpeg.' in src:
		ext = '.jpeg'
	elif 'http://videos-mp4.' in src:
		ext = '.mp4'
	else:
		ext = '.mp3'
		
	file_path = directory + case_name + ext
	file = Path(file_path)

	#Чтобы не скачивать файлы, которые уже есть, мы проверяем соответствие размеров, для этого вычисляем эти переменные	
	if file.is_file():
		file_server_size = int(os.path.getsize(file_path))
		file_target_size = int(r.headers.get('content-length', 0))
		
		#Размеры отличаются, значит скачиваем
		if file_server_size != file_target_size:
			with open(file_path, "wb") as file:
				for chunk in r.iter_content(chunk_size=1024):
					if chunk:
						file.write(chunk)
						pbar.update(1024)
		else:
			print("We've got that file on the server already!")
	else:
		#Если такого файла нет на сервере, тоже скачиваем
		with open(file_path, "wb") as file:
			for chunk in r.iter_content(chunk_size=1024):
				if chunk:
					file.write(chunk)
					pbar.update(1024)
        
#Приводим названия категорий к единому формату
def award_fix(award_level):
	Titanium = ['Titanium Lion']
	GPrix = ['Grand Prix ', 'Grand Prix Campaign', 'Grand Prix for Good', 'Titanium Grand Prix ']
	Gold = ['Gold Lion', 'Gold  Lion Campaign', 'Gold Lion Campaign']
	Silver = ['Silver  Lion', 'Silver Lion', 'Silver Lion Campaign']
	Bronze = ['Bronze Lion', 'Bronze Lion Campaign']
	Shortlist = ['Shortlist']
	
	if award_level in Titanium:
		return 'Gold Lion'
	elif award_level in GPrix:
		return 'Grand Prix'
	elif award_level in Gold:
		return 'Gold Lion'
	elif award_level in Silver:
		return 'Silver Lion'
	elif award_level in Bronze:
		return 'Bronze Lion'
	elif award_level in Shortlist:
		return 'Shortlist'
	else:
		return award_level

categories = [
	'creative-effectiveness',
	'cyber',
	'design',
	'digital-craft',
	'direct',
	'film',
	'film-craft',
	'glass-lion',
##	'grand-prix-for-good',
	'integrated',
	'media',
	'mobile',
	'outdoor',
	'pr',
	'print-and-publishing',
	'product-design',
	'promo-and-activation',
	'radio',
	'titanium',
	'creative-data',
	'innovation',
##	'grand-prix-for-good-health',
	'health-and-wellness',
	'pharma',
	'entertainment',
	'entertainment-for-music'
]	

Titanium = ['Titanium Grand Prix ', 'Titanium Lion']
GPrix = ['Grand Prix ', 'Grand Prix Campaign', 'Grand Prix for Good']
Gold = ['Gold Lion', 'Gold  Lion Campaign', 'Gold Lion Campaign']
Silver = ['Silver  Lion', 'Silver Lion', 'Silver Lion Campaign']
Bronze = ['Bronze Lion', 'Bronze Lion Campaign']
Shortlist = ['Shortlist']

info_dict = {}
for category in categories:
	
	count = 1
	award_req = Titanium + GPrix + Gold + Silver + Bronze
	case_array = get_case_info(category, award_req)

	info_dict[category] = {
		'Grand Prix':{
			'Audio':0,
			'Video':0,
			'Image':0,
			'Error':0,
			'Duplicate':0,
			'Video list':[],
			'Image list':[],
			'Error list':[],
			'Duplicate list':[]
		},
		'Gold Lion':{
			'Audio':0,
			'Video':0,
			'Image':0,
			'Error':0,
			'Duplicate':0,
			'Video list':[],
			'Image list':[],
			'Error list':[],
			'Duplicate list':[]
		},
		'Silver Lion':{
			'Audio':0,
			'Video':0,
			'Image':0,
			'Error':0,
			'Duplicate':0,
			'Video list':[],
			'Image list':[],
			'Error list':[],
			'Duplicate list':[]
		},
		'Bronze Lion':{
			'Audio':0,
			'Video':0,
			'Image':0,
			'Error':0,
			'Duplicate':0,
			'Video list':[],
			'Image list':[],
			'Error list':[],
			'Duplicate list':[]
		},
		'Shortlist':{
			'Audio':0,
			'Video':0,
			'Image':0,
			'Error':0,
			'Duplicate':0,
			'Video list':[],
			'Image list':[],
			'Error list':[],
			'Duplicate list':[]
		}
	}
	
	unique_cases_list = []
	
	for case in case_array:
	
		print('')
		number = case['number']
		case_name = case['case_name']
		award_level = award_fix(case['award_level'])

		print(str(count) + ' out of ' + str(len(case_array)))
		print('Downloading ' + case_name + ' to /' + category + "/" + award_level + '...')
		#Некоторые кейсы побеждают в одной категории, но разных подкатегориях
		#Мы их пропускаем и не скачиваем
		if [case_name, award_level] not in unique_cases_list:

			unique_cases_list.append([case_name, award_level])
			
			src = get_content_src(category, number)
			#Добавляем номер кейса в название файла,
			#чтобы элементы одной кампании шли друг за другом
			case_name = str(count) + ' ' + case_name			
			if 'http://images-jpeg.' in src:		
				download_file(category, case_name, src, award_level)
				info_dict[category][award_fix(award_level)]['Image'] += 1
			elif 'http://videos-mp4.' in src:
				download_file(category, case_name, src, award_level)
				info_dict[category][award_fix(award_level)]['Video'] += 1
			elif 'http://originals-all.' in src:
				download_file(category, case_name, src, award_level)
				info_dict[category][award_fix(award_level)]['Audio'] += 1				
			else:
				print('No file found')
				info_dict[category][award_fix(award_level)]['Error'] += 1
				info_dict[category][award_fix(award_level)]['Error list'] += [case_name]
		else:
			print("It's a duplicate, so skip it")
			case_name = str(count) + ' ' + case_name
			info_dict[category][award_fix(award_level)]['Duplicate'] += 1
			info_dict[category][award_fix(award_level)]['Duplicate list'] += [case_name]

		#Считаем количество кейсов
		count += 1
	
	pprint.pprint(info_dict[category])
	with open('./cannes/' + category+ '/cannes_log_' + category + '.txt', 'wt') as log:
	    pprint.pprint(info_dict[category], stream=log)

with open('cannes_log.txt', 'wt') as log:
    pprint.pprint(info_dict, stream=log)