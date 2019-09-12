import requests
import base64
import time
import os
import pickle
import re
from collections import namedtuple
import prettytable as pt
import urllib.parse
import datetime
import json


class User:
    def __init__(self):
        self.headers = {
            'Accept': '*/*',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': 'https://kyfw.12306.cn',
            'Referer': 'https://kyfw.12306.cn/otn/resources/login.html',
            'Sec-Fetch-Mode': 'cors',
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.132 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
        }
        self.ss = requests.Session()
        self.ss.headers = self.headers

        self.uuid = None
        self.apptk = None

        self.repeat_submit_token = None
        self.seat_types = None
        self.ticket_info_for_passenger_form = None
        self.normal_passengers = None
        self.order_id = None

    def _create_qr64(self):
        url = 'https://kyfw.12306.cn/passport/web/create-qr64'
        data = {'appid': 'otn'}
        r = self.ss.post(url, data=data)
        r_json = r.json()
        print(r_json['result_message'])
        if r_json['result_code'] == '0':
            with open('qr64.jpg', 'wb') as f:
                f.write(base64.b64decode(r_json['image']))
            self.uuid = r_json['uuid']
            # print('uuid:', self.uuid)
            os.system('start qr64.jpg')

    def _check_qr(self):
        url = 'https://kyfw.12306.cn/passport/web/checkqr'
        data = {
            'appid': 'otn',
            'uuid': self.uuid,
        }
        r = self.ss.post(url, data=data)
        r_json = r.json()
        print(r_json['result_message'])
        return r_json['result_code']

    def _uamtk(self):
        print('uamtk', end=' ')
        url = 'https://kyfw.12306.cn/passport/web/auth/uamtk'
        data = {'appid': 'otn'}
        r = self.ss.post(url, data=data)
        r_json = r.json()
        print(r_json['result_message'])
        if r_json['result_code'] == 0:
            self.apptk = r_json['newapptk']
            # print(self.apptk)

    def _uamauthclient(self):
        print('uamauthclient', end=' ')
        url = 'https://kyfw.12306.cn/otn/uamauthclient'
        data = {
            'tk': self.apptk
        }
        self.ss.headers['Content-Length'] = '47'
        r = self.ss.post(url, data=data)
        del self.ss.headers['Content-Length']
        try:
            r_json = r.json()
            print(r_json['result_message'])
            if r_json['result_code'] == 0:
                print(r_json['username'])
        except:
            print(r.text)

    def _check_is_login(self):
        url = 'https://kyfw.12306.cn/otn/login/conf'
        r = self.ss.get(url)
        if r.json()['data']['is_login'] == 'Y':
            print('登录成功')
            return 1
        else:
            print('登录失败', r.text)
            return 0

    def login(self):
        if os.path.exists('12306.pkl'):
            if self.login_by_cookies():
                return 1

        url = 'https://kyfw.12306.cn/otn/resources/login.html'
        self.ss.get(url)

        self._create_qr64()
        while True:
            result_code = self._check_qr()
            if result_code == '2':
                break
            time.sleep(1)

        self._uamtk()
        self._uamauthclient()

        if not self._check_is_login():
            return 0

        with open('12306.pkl', 'wb') as f:
            pickle.dump(self.ss.cookies, f)

        return 1

    def login_by_cookies(self):
        with open('12306.pkl', 'rb') as f:
            self.ss.cookies = pickle.load(f)

        if not self._check_is_login():
            return 0
        return 1

    def _check_user(self):
        print('检查用户登录状态')
        url = 'https://kyfw.12306.cn/otn/login/checkUser'
        r = self.ss.post(url, data={'_json_att': ''})
        if not r.json()['data']['flag']:
            print(r.text)
            return 0
        return 1

    def _submit_order_request(self, train_info, ticket_common):
        print('提交车票预订信息')
        url = 'https://kyfw.12306.cn/otn/leftTicket/submitOrderRequest'
        data = {
            'back_train_date': '',
            'purpose_codes': ticket_common['purpose_codes'],
            'query_from_station_name': ticket_common['from_station'],
            'query_to_station_name': ticket_common['to_station'],
            'secretStr': urllib.parse.unquote(train_info.secret_str),
            'tour_flag': 'dc',
            'train_date': ticket_common['train_date'],
            'undefined': ''
        }
        r = self.ss.post(url, data=data)
        if r.json()['data'] != 'N':
            print(r.text)
            return 0
        return 1

    def _init_dc(self):
        print('初始化页面')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/initDc'
        try:
            r = self.ss.post(url, data={'_json_att': ''})
            self.repeat_submit_token = re.search(r"var\sglobalRepeatSubmitToken\s=\s'(.+?)'", r.text).group(1)
            self.seat_types = eval(re.search(r"var\sinit_seatTypes=(.+?);", r.text).group(1).replace('null', "'null'"))
            tmp = re.search(r"var\sticketInfoForPassengerForm=(.+?);", r.text).group(1)
            tmp = tmp.replace('null', "'null'")
            tmp = tmp.replace('true', 'True')
            tmp = tmp.replace('false', 'False')
            self.ticket_info_for_passenger_form = eval(tmp)
            for st in self.seat_types:
                print(st['value'], st['id'])
        except:
            return 0
        return 1

    def _get_passenger_dtos(self):
        print('获取乘客信息')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getPassengerDTOs'
        data = {
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': self.repeat_submit_token,
        }
        while True:
            r = self.ss.post(url, data=data)
            try:
                self.normal_passengers = r.json()['data']['normal_passengers']
                break
            except json.decoder.JSONDecodeError:
                with open(url.split('/')[-1]+'.txt', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print('重试')
                continue
        for p in self.normal_passengers:
            print(p['passenger_name'], end=' ')
        print()

    def _check_order_info(self, passenger, seat_id):
        print('确认订单信息')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/checkOrderInfo'
        name = passenger['passenger_name']
        id_no = passenger['passenger_id_no']
        mobile_no = passenger['mobile_no']
        allenc_str = passenger['allEncStr']
        seat_type_s = seat_id + ',0,1,'
        data = {
            '_json_att': '',
            'bed_level_order_num': '000000000000000000000000000000',
            'cancel_flag': '2',
            'oldPassengerStr': name + ',1,' + id_no + ',1_',
            'passengerTicketStr': seat_type_s + name + ',1,' + id_no + ',' + mobile_no + ',N,' + allenc_str,
            'REPEAT_SUBMIT_TOKEN': self.repeat_submit_token,
            'randCode': '',
            'tour_flag': self.ticket_info_for_passenger_form['tour_flag'],
            'whatsSelect': '1',
        }
        while True:
            r = self.ss.post(url, data=data)
            try:
                if not r.json()['data']['submitStatus']:
                    print(r.text)
                break
            except json.decoder.JSONDecodeError:
                with open(url.split('/')[-1]+'.txt', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print('重试')
                continue

    def _get_queue_count(self, train_info, seat_id, train_date):
        print('提交预订请求')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/getQueueCount'
        train_date = datetime.datetime.strptime(train_date, "%Y-%m-%d").date()
        train_date = train_date.strftime("%a %b %d %Y") + ' 00:00:00 GMT+0800 (中国标准时间)'
        data = {
            '_json_att': '',
            'fromStationTelecode': train_info.from_station_telecode,
            'leftTicket': train_info.left_ticket,
            'purpose_codes': self.ticket_info_for_passenger_form['purpose_codes'],
            'REPEAT_SUBMIT_TOKEN': self.repeat_submit_token,
            'seatType': seat_id,
            'stationTrainCode': train_info.train_code,
            'toStationTelecode': train_info.from_station_telecode,
            'train_date': train_date,
            'train_location': train_info.train_location,
            'train_no': train_info.train_no,
        }
        while True:
            r = self.ss.post(url, data=data)
            try:
                print(r.json()['data']['ticket'])
                break
            except json.decoder.JSONDecodeError:
                with open(url.split('/')[-1]+'.txt', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print('重试')
                continue

    def _confirm_single_for_queue(self, train_info, passenger, seat_id, choose_seats=''):
        print('检查提交状态')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/confirmSingleForQueue'
        name = passenger['passenger_name']
        id_no = passenger['passenger_id_no']
        mobile_no = passenger['mobile_no']
        allenc_str = passenger['allEncStr']
        seat_type_s = seat_id + ',0,1,'
        data = {
            '_json_att': '',
            'choose_seats': choose_seats,
            'dwAll': 'N',
            'key_check_isChange': self.ticket_info_for_passenger_form['key_check_isChange'],
            'leftTicketStr': train_info.left_ticket,
            'oldPassengerStr': name + ',1,' + id_no + ',1_',
            'passengerTicketStr': seat_type_s + name + ',1,' + id_no + ',' + mobile_no + ',N,' + allenc_str,
            'purpose_codes': self.ticket_info_for_passenger_form['purpose_codes'],
            'randCode': '',
            'REPEAT_SUBMIT_TOKEN': self.repeat_submit_token,
            'roomType': '00',
            'seatDetailType': '000',
            'train_location': train_info.train_location,
            'whatsSelect': '1'
        }
        while True:
            r = self.ss.post(url, data=data)
            try:
                if not r.json()['data']['submitStatus']:
                    print(r.text)
                break
            except json.decoder.JSONDecodeError:
                with open(url.split('/')[-1]+'.txt', 'w', encoding='utf-8') as f:
                    f.write(r.text)
                print('重试')
                continue

    def _query_order_wait_time(self):
        print('排队等待')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/queryOrderWaitTime'
        params = {
            'random': int(time.time() * 1000),
            'tourFlag': 'dc',
            '_json_att': '',
            'REPEAT_SUBMIT_TOKEN': self.repeat_submit_token,
        }
        while True:
            params['random'] = int(time.time() * 1000)
            r = self.ss.get(url, params=params)
            data = r.json()['data']
            if data.get('orderId'):
                self.order_id = data['orderId']
                print(self.order_id)
                break
            time.sleep(1)

    def _result_order_for_queue(self):
        print('请求预订结果')
        url = 'https://kyfw.12306.cn/otn/confirmPassenger/resultOrderForDcQueue'
        params = {
            '_json_att': '',
            'orderSequence_no': self.order_id,
            'REPEAT_SUBMIT_TOKEN': self.repeat_submit_token,
        }
        r = self.ss.get(url, params=params)
        if not r.json()['data']['submitStatus']:
            print(r.text)
        else:
            print('预定成功')

    def order_ticket(self, train_info, ticket_common, order_info):
        cookie_s = ''
        for k, v in self.ss.cookies.items():
            s = k + '=' + v + '; '
            cookie_s += s
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "0",
            "Cookie": cookie_s,
            "Host": "kyfw.12306.cn",
            "Origin": "https://kyfw.12306.cn",
            "Referer": "https://kyfw.12306.cn/otn/view/information.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/73.0.3683.86 Safari/537.36",
        }
        self.ss.headers = headers
        if not self._check_user():
            return 0
        if not self._submit_order_request(train_info, ticket_common):
            return 0
        if not self._init_dc():
            return 0
        self._get_passenger_dtos()

        passenger_name, seat = order_info.split(',')
        passenger = None
        seat_id = None
        for psg in self.normal_passengers:
            if psg['passenger_name'] == passenger_name:
                passenger = psg
                break
        for st in self.seat_types:
            if st['value'] == seat:
                seat_id = st['id']
                break
        if passenger is None:
            print('没有此乘客信息')
            return 0
        if seat_id is None:
            print('没有此座位')
            return 0

        self._check_order_info(passenger, seat_id)
        self._get_queue_count(train_info, seat_id, ticket_common['train_date'])
        self._confirm_single_for_queue(train_info, passenger, seat_id)
        self._query_order_wait_time()
        self._result_order_for_queue()

        return 1


class Ticket:
    station_names = dict()

    def __init__(self):
        self.TrainInfo = namedtuple('TrainInfo', [
            'secret_str', 'from_station_telecode', 'to_station_telecode', 'left_ticket', 'train_no', 'train_location', 'train_date',
            'train_code', 'from_station', 'to_station', 'from_time', 'to_time', 'time_taken',
            'tdz', 'ydz', 'edz', 'gjrw', 'rw', 'dw', 'yw', 'rz', 'yz', 'wz', 'other'
        ])
        self.train_list = list()
        self.common = dict()

    @classmethod
    def get_station_name(cls):
        url = 'https://kyfw.12306.cn/otn/resources/js/framework/station_name.js?station_version=1.9109'
        # r = requests.get(url, verify=False)
        r = requests.get(url)
        station_name_list = re.search(r"var\s*station_names\s*=\s*'(.+?)'", r.text).group(1).split('|')
        length = len(station_name_list)
        for i in range(0, length-1, 5):
            Ticket.station_names[station_name_list[i+1]] = station_name_list[i+2]

    def query_ticket(self, train_date, from_station, to_station, passenger_type):
        self.common['from_station'] = from_station
        self.common['to_station'] = to_station
        self.common['purpose_codes'] = passenger_type
        self.common['train_date'] = train_date
        url = 'https://kyfw.12306.cn/otn/leftTicket/queryA'
        params = {
            'leftTicketDTO.train_date': train_date,
            'leftTicketDTO.from_station': Ticket.station_names[from_station],
            'leftTicketDTO.to_station': Ticket.station_names[to_station],
            'purpose_codes': passenger_type,
        }
        # r = requests.get(url, params=params, verify=False)
        r = requests.get(url, params=params)
        r_json = r.json()
        if r_json['status']:
            station_map = r_json['data']['map']
            result = r_json['data']['result']
            for item in result:
                fields = item.split('|')
                train_info = self.TrainInfo(
                    fields[0], fields[6], fields[7], fields[12], fields[2], fields[15], fields[13],
                    fields[3], station_map[fields[6]], station_map[fields[7]], fields[8], fields[9], fields[10],
                    fields[32], fields[31], fields[30], fields[21], fields[23], fields[33],
                    fields[28], fields[24], fields[29], fields[26], fields[25]
                )
                self.train_list.append(train_info)
        else:
            print(r.text)

    def show(self):
        tb = pt.PrettyTable([
            '车次', '出发站', '到达站', '出发时间', '到达时间', '历时',
            '商务座/特等座', '一等座', '二等座', '高级软卧', '软卧/一等卧', '动卧', '硬卧/二等卧',
            '软座', '硬座', '无座', '其他'
        ])
        for train_info in self.train_list:
            tb.add_row(['-' if d == '' else d for d in list(train_info._asdict().values())[7:]])
        print(tb)


def main():
    user = User()
    if not user.login():
        return 0

    Ticket.get_station_name()
    ticket = Ticket()
    ticket.query_ticket('2019-09-19', '上海', '海口', 'ADULT')
    ticket.show()

    order_dict = {'K511': '邓儒超,软卧'}
    train_list = list()
    for train in ticket.train_list:
        if train.train_code in order_dict:
            train_list.append(train)
    for train in train_list:
        if not user.order_ticket(train, ticket.common, order_dict[train.train_code]):
            return 0


if __name__ == '__main__':
    main()
