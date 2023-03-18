<?php

if(count($_FILES) < 1) exit('No attachment file!');
if(!isset($_FILES['file'])) exit('No attachment file!');
if($_FILES['file']['error'] !== UPLOAD_ERR_OK) exit('Upload error! ('.$_FILES['file']['error'].')');
if(!isset($_POST['at_id'])) exit('No at_id!');
if(!isset($_POST['file_type'])) exit('No file_type!');
if(!isset($_POST['rows'])) exit('No rows!');
if(!isset($_POST['cols'])) exit('No cols!');
if(!isset($_POST['to_url'])) exit('No to_url!');

$db_path = '../ett.db';
if(!is_file($db_path))
{
	exec('sqlite3 '.$db_path.' < ../table.txt');
}

$db = new SQLite3($db_path);
$datemerk = date('YmdHis');
$sql = 'INSERT INTO RECEIPT (AT_ID, NAME, STATUS, ROWS, COLS, FROM_URL, FILE_TYPE, TO_URL, CREATE_DATEMERK, UPDATE_DATEMARK) VALUES (';
$sql .= intval($_POST['at_id']); //AT_ID
$sql .= ',\''.$_FILES['file']['name'].'\''; //NAME
$sql .= ',0'; //STATUS
$sql .= ','.intval($_POST['rows']); //ROWS
$sql .= ','.intval($_POST['cols']); //COLS
$sql .= ',\''.'\''; //FROM_URL
$sql .= ',\''.mb_strtolower($_POST['file_type']).'\''; //FILE_TYPE
$sql .= ',\''.$_POST['to_url'].'\''; //TO_URL
$sql .= ',\''.$datemerk.'\''; //CREATE_DATEMERK
$sql .= ',\''.$datemerk.'\''; //UPDATE_DATEMARK
$sql .= ')';
$db->exec($sql);

$result = $db->query('select last_insert_rowid()');
$id = $result->fetchArray()['last_insert_rowid()'];
$dir = strval(intval($id / 1000));
if(!is_dir('../'.$dir)) mkdir('../'.$dir);
$result = move_uploaded_file($_FILES['file']['tmp_name'], '../'.$dir.'/'.$id);
if(!$result)
{
	$sql = 'UPDATE RECEIPT SET STATUS = 1, RECEIVE_ERR = \'php move_uploaded_file function error!\' WHERE ID = '.$id;
  $result = $db->query('select last_insert_rowid()');
	exit('NG');
}

$phpexe = 0;
$ps = [];
exec('ps axu', $ps);
for($i = 0; $i < count($ps); $i++) {
  $pos1 = strpos($ps[$i], 'www-data');
  $pos2 = strpos($ps[$i], 'ETT_Service.py');
  if($pos1 !== false && $pos2 !== false) {
    $phpexe = 1;
    break;
  }
}

if($phpexe === 0) exec('python3 ../ETT_Service.py > ../ETT_Service.out 2>&1 &');

echo('debian :OK');

