import csv
import json
import datetime
import glob
import os
import urllib.request
import jsonschema

#日本標準時
JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
#外部ファイルの参照設定
REMOTE_SOURCES = {
    'covid19_data':{
        'url':'https://www.harp.lg.jp/opendata/dataset/1369/resource/2853/covid19_data.csv',
        'type':'csv'
    }
}
#headerの変換一覧
HEADER_TRANSLATIONS = {}
#intにキャストすべきkey
INT_CAST_KEYS = []
#ファイルエンコーディングリスト
CODECS = ['utf-8','cp932','shift_jis','euc_jp',
          'euc_jis_2004','euc_jisx0213',
          'iso2022_jp','iso2022_jp_1','iso2022_jp_2','iso2022_jp_2004','iso2022_jp_3','iso2022_jp_ext',
          'shift_jis_2004','shift_jisx0213',
          'utf_16','utf_16_be','utf_16_le','utf_7','utf_8_sig']

#バリデーション用のスキーマ定義
import schemas
SCHEMAS = schemas.SCHEMAS

class CovidDataIntegrater:
    def __init__(self):
        self.data = {}
    
    #REMOTE_SOURCESに基づき外部ファイルにアクセス・データ取得
    def fetch_datas(self):
        for key in REMOTE_SOURCES:
            self.fetch_data_of(key)

    def fetch_data_of(self, key):
        datatype = REMOTE_SOURCES[key]['type']
        dataurl = REMOTE_SOURCES[key]['url']
        data = {}
        if datatype == 'odp':
            data = self.import_odp_csv(key, dataurl)
        elif datatype == 'csv':
            data = self.import_csv_from(dataurl)
        
        self.data[key] = data

    def export_json_of(self, key, directory='data/'):
        with open(directory + key + '.json', 'w', encoding='utf-8') as f:
            json.dump(self.data[key], f, indent=4, ensure_ascii=False)

    def export_jsons(self, directory='data/'):
        for key in self.data:
            print(key + '.json')
            self.export_json_of(key, directory)

    #CSV文字列を[dict]型に変換
    def csvstr_to_dicts(self, csvstr)->list:
        datas = []
        rows = [row for row in csv.reader(csvstr.splitlines())]
        header = rows[0]
        header = self.translate_header(header)
        maindatas = rows[1:]
        for d in maindatas:
            #空行をスキップ
            if d == []:
                continue
            data = {}
            for i in range(len(header)):
                data[header[i]] = d[i]
                #特定のカラムのデータを整数値にキャスト
                if header[i] in INT_CAST_KEYS:
                    data[header[i]] = int(d[i])
            datas.append(data)
        return datas

    #生成されるjsonの正当性チェック
    def validate(self):
        for key in self.data:
            jsonschema.validate(self.data[key], SCHEMAS[key])

    #HEADER_TRANSLATIONSに基づきデータのヘッダ(key)を変換
    def translate_header(self, header:list)->list:
        for i in range(len(header)):
            for key in HEADER_TRANSLATIONS:
                if header[i] == key:
                    header[i] = HEADER_TRANSLATIONS[key]
        return header

    #デコード出来るまでCODECS内全コーデックでトライする
    def decode_csv(self, csv_data)->str:
        print('csv decoding')
        for codec in CODECS:
            try:
                csv_str = csv_data.decode(codec)
                print('ok:' + codec)
                return csv_str
            except:
                print('ng:' + codec)
                continue
        print('Appropriate codec is not found.')

    #外部のCSVファイルをインポート url=xxxx/xxxx.csv
    def import_csv_from(self, csvurl):
        request_file = urllib.request.urlopen(csvurl)
        if not request_file.getcode() == 200:
            return
        
        f = self.decode_csv(request_file.read())
        filename = os.path.splitext(os.path.basename(csvurl))[0]
        datas = self.csvstr_to_dicts(f)

        return {
            'data': datas,
            'last_update': datetime.datetime.now(JST).isoformat()
        }

    def generate_current_patients(self, covid19_data):
        current_patients = {
            'data':[],
            'last_update':datetime.datetime.now(JST).isoformat()
        }

        data_keys = [
            '日患者数',
            '日軽症中等症数',
            '日重症数',
            '日死亡数'
        ]
        
        for d in covid19_data:
            for key in data_keys:
                #current_patientsだけは空データを0埋めする
                if d[key] == '':
                    d[key] = "0"

            daily_data = {
                '日付':self.make_datetime_str(d['年'],d['月'],d['日']),
                '患者数':int(d['日患者数']),
                '軽症中等症':int(d['日軽症中等症数']),
                '重症':int(d['日重症数']),
                '死亡':int(d['日死亡数'])
            }

            current_patients['data'].append(daily_data)

        self.data['current_patients'] = current_patients
    
    def generate_discharges_summary(self, covid19_data):
        discharges_summary = {
            'data':[],
            'last_update':datetime.datetime.now(JST).isoformat()
        }
        
        for d in covid19_data:
            try:
                daily_data = {
                    '日付':self.make_datetime_str(d['年'],d['月'],d['日']),
                    '日治療終了数':int(d['日治療終了数'])
                }
            except:
                continue
            discharges_summary['data'].append(daily_data)

        self.data['discharges_summary'] = discharges_summary

    def generate_inspections(self, covid19_data):
        inspections = {
            'data':[],
            'last_update':datetime.datetime.now(JST).isoformat()
        }
        
        for d in covid19_data:
            try:
                daily_data = {
                    '日付':self.make_datetime_str(d['年'],d['月'],d['日']),
                    '日検査数':int(d['日検査数'])
                }
            except:
                continue
            inspections['data'].append(daily_data)

        self.data['inspections'] = inspections

    def generate_patients_summary(self, covid19_data):
        patients_summary = {
            'data':[],
            'last_update':datetime.datetime.now(JST).isoformat()
        }
        
        for d in covid19_data:
            try:
                daily_data = {
                    '日付':self.make_datetime_str(d['年'],d['月'],d['日']),
                    '日陽性数':int(d['日陽性数'])
                }
            except:
                continue
            patients_summary['data'].append(daily_data)

        self.data['patients_summary'] = patients_summary

    #iso-8601の年月日文字列生成：yyyy-mm-dd
    def make_datetime_str(self, year, month, day)->str:
        #ゼロ埋め2桁
        mm = month.zfill(2)
        dd = day.zfill(2)
        return str(year) + '-' + str(mm) + '-' + str(dd)

    def generate_main_summary(self):
        #検査数
        inspection_sum = 0
        inspections = self.data['inspections']['data']
        for i in inspections:
            inspection_sum += i['日検査数']

        #陽性者数
        patients_sum = 0
        patients_summary = self.data['patients_summary']['data']
        for p in patients_summary:
            patients_sum += p['日陽性数']


        #患者数、軽症・中等症者数、重傷者数、死亡者数
        current_patients_sum = 0
        mild_patients_sum = 0
        critical_patients_sum = 0
        dead_patients_sum = 0
        current_patients = self.data['current_patients']['data']
        for c in current_patients:
            if not c['患者数']  == '':
                current_patients_sum += c['患者数']
            if not c['軽症中等症']  == '':
                mild_patients_sum += c['軽症中等症']
            if not c['重症']  == '':
                critical_patients_sum += c['重症']
            if not c['死亡']  == '':
                dead_patients_sum += c['死亡']

        #陰性確認者数
        discharges_sum = 0
        discharges_summary = self.data['discharges_summary']['data']
        for d in discharges_summary:
            discharges_sum += d['日治療終了数']

        main_summary = {
            '検査人数':inspection_sum,
            '陽性者数':patients_sum,
            '患者数':current_patients_sum,
            '軽症・中等症者数':mild_patients_sum,
            '重傷者数':critical_patients_sum,
            '死亡者数':dead_patients_sum,
            '陰性確認数':discharges_sum
        }

        self.data['main_summary'] = main_summary

    def generate_datas(self):
        print('current_patients')
        self.generate_current_patients(self.data['covid19_data']['data'])
        print('discharges_summary')
        self.generate_discharges_summary(self.data['covid19_data']['data'])
        print('patients_summary')
        self.generate_patients_summary(self.data['covid19_data']['data'])
        print('inspections')
        self.generate_inspections(self.data['covid19_data']['data'])
        print('main_summary')
        self.generate_main_summary()

if __name__ == "__main__":
    dm = CovidDataIntegrater()
    print('---fetch data---')
    #REMOTE_SOUCESのすべてのソースにアクセス・データ取得しself.dataに保存
    dm.fetch_datas()
    print('---done---')
    print('---generate datas---')
    #covid19_data.csvのデータを集計してpatients以外のデータを生成しself.dataに保存
    dm.generate_datas()
    print('---done---')
    print('---export jsons---')
    #dict型であるself.dataの全要素がスキーマ定義に適合するかチェック
    dm.validate()
    #self.dataの全要素をjson形式で出力
    dm.export_jsons()
    print('---done---')