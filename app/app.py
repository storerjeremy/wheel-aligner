import json
import logging
import threading
import time
import math

from flask import *

from lib import BNO055

# Uncomment for prod
# bno = BNO055.BNO055()

BNO_UPDATE_FREQUENCY_HZ = 10

CALIBRATION_FILE = 'calibration.json'

BNO_AXIS_REMAP = { 'x': BNO055.AXIS_REMAP_X,
                   'y': BNO055.AXIS_REMAP_Y,
                   'z': BNO055.AXIS_REMAP_Z,
                   'x_sign': BNO055.AXIS_REMAP_POSITIVE,
                   'y_sign': BNO055.AXIS_REMAP_POSITIVE,
                   'z_sign': BNO055.AXIS_REMAP_NEGATIVE }

app = Flask(__name__)

bno_data = {}
bno_changed = threading.Condition()
bno_thread = None


def read_bno():
    while True:
        temp = bno.read_temp()
        heading, roll, pitch = bno.read_euler()
        x, y, z, w = bno.read_quaternion()
        sys, gyro, accel, mag = bno.get_calibration_status()
        status, self_test, error = bno.get_system_status(run_self_test=False)

        if error != 0:
            print('Error! Value: {0}'.format(error))

        with bno_changed:
            bno_data['euler'] = (heading, roll, pitch)
            bno_data['temp'] = temp
            bno_data['quaternion'] = (x, y, z, w)
            bno_data['calibration'] = (sys, gyro, accel, mag)
            bno_changed.notifyAll()

        time.sleep(1.0/BNO_UPDATE_FREQUENCY_HZ)


def bno_sse():
    while True:

        with bno_changed:
            bno_changed.wait()
            heading, roll, pitch = bno_data['euler']
            temp = bno_data['temp']
            x, y, z, w = bno_data['quaternion']
            sys, gyro, accel, mag = bno_data['calibration']

        data = {'heading': heading, 'roll': roll, 'pitch': pitch, 'temp': temp,
                'quatX': x, 'quatY': y, 'quatZ': z, 'quatW': w,
                'calSys': sys, 'calGyro': gyro, 'calAccel': accel, 'calMag': mag,}

        yield 'data: {0}\n\n'.format(json.dumps(data))


# Uncomment for prod
# @app.before_first_request
# def start_bno_thread():
#     global bno_thread
#     if not bno.begin(BNO055.OPERATION_MODE_IMUPLUS):
#         raise RuntimeError('Failed to initialize BNO055!')
#     bno_thread = threading.Thread(target=read_bno)
#     bno_thread.daemon = True
#     bno_thread.start()


@app.route('/bno')
def bno_path():
    return Response(bno_sse(), mimetype='text/event-stream')


@app.route('/save_calibration', methods=['POST'])
def save_calibration():
    with bno_changed:
        data = bno.get_calibration()

    with open(CALIBRATION_FILE, 'w') as cal_file:
        json.dump(data, cal_file)

    return 'OK'


@app.route('/load_calibration', methods=['POST'])
def load_calibration():
    with open(CALIBRATION_FILE, 'r') as cal_file:
        data = json.load(cal_file)

    with bno_changed:
        bno.set_calibration(data)

    return 'OK'


@app.route('/wheel-alignment')
def wheel_alignment():
    return render_template('wheel-alignment.html')


@app.route('/')
def home():
    return render_template('home.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)
