import os
import math
import shutil
import subprocess
import time
#import MySQLdb
import sqlite3
import requests
import base64
import cv2

kTMP_DIR = 'ett_tmp_dir'

def db_connect():
  con = sqlite3.connect('ett.db')
  con.row_factory = sqlite3.Row
  cursor = con.cursor()
  return con, cursor

def send_back_sd(db_receipt, pdf_text):
  url = 'http://' + db_receipt['TO_URL']

  fileName = os.path.join(kTMP_DIR, '{}-tile.png'.format(db_receipt['ID']))
  if not os.path.exists(fileName): fileName = os.path.join(kTMP_DIR, '{}-tile-0.png'.format(db_receipt['ID']))

  fileDataBinary = open(fileName, 'rb').read()
  base64_bytes = base64.b64encode(fileDataBinary)
  params = {'at_id':db_receipt['AT_ID'], 'at_thumb_base64':base64_bytes.decode('utf-8'), 'at_filetext':pdf_text}
  response = requests.post(url, data=params)

  if response.content.decode('utf-8') == 'END':
    success_send_back_sd(db_receipt)
  else:
    error_send_back_sd(db_receipt, 'sd send back error!')

def success_send_back_sd(db_receipt):
  con, cursor = db_connect()
  cursor.execute('UPDATE RECEIPT SET STATUS = 5 WHERE ID = ?', (db_receipt['ID'],))
  con.commit()
  cursor.close()
  con.close()

def error_send_back_sd(db_receipt, msg):
  con, cursor = db_connect()
  cursor.execute('UPDATE RECEIPT SET STATUS = 4, SENDBACK_ERR = ? WHERE ID = ?', (msg, db_receipt['ID']))
  con.commit()
  cursor.close()
  con.close()

def success_extract(db_receipt, num_of_pages):
  con, cursor = db_connect()
  cursor.execute('UPDATE RECEIPT SET STATUS = 2, NUMOFPAGES = ? WHERE ID = ?', (num_of_pages, db_receipt['ID']))
  con.commit()
  cursor.close()
  con.close()

def error_extract(db_receipt, msg):
  con, cursor = db_connect()
  cursor.execute('UPDATE RECEIPT SET STATUS = 3, EXTRACT_ERR = ? WHERE ID = ?', (msg, db_receipt['ID']))
  con.commit()
  cursor.close()
  con.close()

def convert_image_file(dir_no, db_receipt):
  src_path = os.path.join(dir_no, str(db_receipt['ID']))
  ret = subprocess.run(['convert', '-resize', '246x2460', src_path, os.path.join(kTMP_DIR, '{}-tile.png'.format(db_receipt['ID']))], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  if ret.returncode != 0:
    error_extract(db_receipt, ret.stderr) #失敗ログをDB保存
    return

  success_extract(db_receipt, 1)
  send_back_sd(db_receipt, '')

def convert_video_file(dir_no, db_receipt):
  src_path = os.path.join(dir_no, str(db_receipt['ID']))

  cap = cv2.VideoCapture(src_path)
  count = cap.get(cv2.CAP_PROP_FRAME_COUNT);
  if count <= 0: return

  fcount = math.ceil(count / 5)
  for i in range(1, 5):
    frame_num = fcount * i
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ret, frame = cap.read()
    if ret: cv2.imwrite(os.path.join(kTMP_DIR, '{}-{}.png'.format(db_receipt['ID'], i)), frame)

    ret = subprocess.run(['convert', '-resize', '123x1230', os.path.join(kTMP_DIR, '{}-{}.png'.format(db_receipt['ID'], i)), os.path.join(kTMP_DIR, '{}-{}s.png'.format(db_receipt['ID'], i))], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  tile_size = '{}x{}'.format(db_receipt['ROWS'], db_receipt['COLS'])
  exe = ['montage', '-tile', tile_size, '-resize', '100%', '-geometry', '+0+0', os.path.join(kTMP_DIR, '{}-*s.png'.format(db_receipt['ID'])), os.path.join(kTMP_DIR, '{}-tile.png'.format(db_receipt['ID']))]
  ret = subprocess.run(exe, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if ret.returncode != 0:
    error_extract(db_receipt, ret.stderr) #失敗ログをDB保存
    return

  success_extract(db_receipt, 4)
  send_back_sd(db_receipt, '')

def convert_office_file(dir_no, db_receipt):
  src_path = os.path.join(dir_no, str(db_receipt['ID']))
  exe = ['libreoffice', '--headless', '--convert-to', 'pdf', src_path, '--outdir', kTMP_DIR]
  ret = subprocess.run(exe, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if ret.returncode != 0:
    error_extract(db_receipt, ret.stderr) #失敗ログをDB保存
    return False, src_path

  src_path = os.path.join(kTMP_DIR, '{}.pdf'.format(db_receipt['ID']))
  return True, src_path

def extract_pdf(db_receipt, src_path):
  dist_path = os.path.join(kTMP_DIR, str(db_receipt['ID']))

  ret = subprocess.run(['pdftocairo', '-png', '-f', '1', '-l', '4', src_path, dist_path], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if ret.returncode != 0:
    error_extract(db_receipt, ret.stderr) #失敗ログをDB保存
    return

  img_files = os.listdir(kTMP_DIR)
  num_of_pages = len(img_files)

  for img_file in img_files:
    ret = subprocess.run(['convert', '-resize', '123x1230', os.path.join(kTMP_DIR, img_file), os.path.join(kTMP_DIR, img_file.replace('.png', 's.png'))], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

  tile_size = '{}x{}'.format(db_receipt['ROWS'], db_receipt['COLS'])
  exe = ['montage', '-tile', tile_size, '-resize', '100%', '-geometry', '+0+0', os.path.join(kTMP_DIR, '{}-*s.png'.format(db_receipt['ID'])), os.path.join(kTMP_DIR, '{}-tile.png'.format(db_receipt['ID']))]
  ret = subprocess.run(exe, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  #if ret.returncode != 0:
  #  error_extract(db_receipt, ret.stderr) #失敗ログをDB保存
  #  return

  ret = subprocess.run(['pdftotext', src_path], encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if ret.returncode != 0:
    error_extract(db_receipt, ret.stderr) #失敗ログをDB保存
    return

  txt_path = src_path.replace('.pdf', '')
  pdf_text = open('{}.txt'.format(txt_path)).read()

  success_extract(db_receipt, num_of_pages)
  send_back_sd(db_receipt, pdf_text)

during_file_name = 'ett_py_exe.txt'
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if not os.path.exists(during_file_name):
  f = open(during_file_name, 'w')
  f.write('ett_py_exe')
  f.close()

while(os.path.exists(during_file_name)):
  con, cursor = db_connect()
  cursor.execute('SELECT * FROM RECEIPT WHERE STATUS = 0')
  db_receipts = cursor.fetchall()
  cursor.close()
  con.close()

  for db_receipt in db_receipts:
    if os.path.exists(kTMP_DIR): shutil.rmtree(kTMP_DIR)
    os.makedirs(kTMP_DIR)

    dir_no = str(math.floor(db_receipt['ID'] / 1000))

    if db_receipt['FILE_TYPE'] == 'pdf':
      src_path = os.path.join(dir_no, str(db_receipt['ID']))
      extract_pdf(db_receipt, src_path)
    elif db_receipt['FILE_TYPE'] == 'docx' or db_receipt['FILE_TYPE'] == 'doc' or db_receipt['FILE_TYPE'] == 'rtf':
      ret, src_path = convert_office_file(dir_no, db_receipt)
      if ret:
        extract_pdf(db_receipt, src_path)
    elif db_receipt['FILE_TYPE'] == 'pptx' or db_receipt['FILE_TYPE'] == 'ppt':
      ret, src_path = convert_office_file(dir_no, db_receipt)
      if ret:
        extract_pdf(db_receipt, src_path)
    elif db_receipt['FILE_TYPE'] == 'xlsx' or db_receipt['FILE_TYPE'] == 'xls':
      ret, src_path = convert_office_file(dir_no, db_receipt)
      if ret:
        extract_pdf(db_receipt, src_path)
    elif db_receipt['FILE_TYPE'] == 'txt' or db_receipt['FILE_TYPE'] == 'html':
      src_path = os.path.join(dir_no, str(db_receipt['ID']))
      exe = ['nkf', '-w', '--overwrite', src_path]
      ret = subprocess.run(exe, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      ret, src_path = convert_office_file(dir_no, db_receipt)
      if ret:
        extract_pdf(db_receipt, src_path)
    elif db_receipt['FILE_TYPE'] == 'wmv' or db_receipt['FILE_TYPE'] == 'mp4' or db_receipt['FILE_TYPE'] == 'avi':
      convert_video_file(dir_no, db_receipt)
    elif db_receipt['FILE_TYPE'] == 'jpg' or db_receipt['FILE_TYPE'] == 'jpeg' or db_receipt['FILE_TYPE'] == 'png' or db_receipt['FILE_TYPE'] == 'bmp':
      convert_image_file(dir_no, db_receipt)
    else:
      error_extract(db_receipt, 'unsupported file type!') #失敗ログをDB保存
      continue

  time.sleep(10)

