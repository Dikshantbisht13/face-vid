###############################################################################
#
# Use this script the extract frames from the MMI Facial Expresssion DB.
# Every n-th frame will be extracted. Frames will be processed in the following
# manner:
# - converted to grey-scale
#   - cropping to detected faces
#   - black oval mask around face
#   - save optical flow along x & y axis
#
# Usage: extract_frames.py <max_frame_count> <path_to_video> <output_path>
#
###############################################################################
from __future__ import generators
import cv2, os, sys, itertools
import numpy as np

CLASSIFIER_PATH = os.path.join(os.path.dirname(sys.argv[0]), "haarcascade_frontalface_alt.xml")
SCALE_FLOW = 10
faceCascade = cv2.CascadeClassifier(CLASSIFIER_PATH)

# Do face detection and return the first face
def detect_face(image):
    faces = faceCascade.detectMultiScale(
        image,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
        flags=cv2.cv.CV_HAAR_SCALE_IMAGE
    )

    if len(faces) == 0:
        sys.exit()

    return faces


# Special processing relevant for the MMI facial dataset
def preprocessMMI(image):
    # turn into greyscale
    imageAsGray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.equalizeHist(imageAsGray)

    imageAsYCrCb = cv2.cvtColor(image, cv2.COLOR_BGR2YCR_CB)  # change the color image from BGR to YCrCb format
    channels = cv2.split(imageAsYCrCb)  # split the image into channels
    channels[0] = cv2.equalizeHist(channels[0])  # equalize histogram on the 1st channel (Y)
    imageWithEqualizedHist = cv2.merge(channels)  # merge 3 channels including the modified 1st channel into one image
    imageAsBGR = cv2.cvtColor(imageWithEqualizedHist,
                              cv2.COLOR_YCR_CB2BGR)  # change the color image from YCrCb to BGR format (to display image properly)

    return (imageAsGray, imageAsBGR)


def read_video(video):
    # read video
    framesGray = []
    framesBGR = []
    cap = cv2.VideoCapture(video)
    frame_count = int(cap.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))

    if cap.isOpened():

        for i in range(0, frame_count):
            # actually read a frame
            returnValue, frame = cap.read()

            if not returnValue:
                break

            (imageAsGray, imageAsBGR) = preprocessMMI(frame)
            framesGray.append(imageAsGray)
            framesBGR.append(imageAsBGR)

        cap.release()
        return (framesGray, framesBGR)
    else:
        sys.exit("Error opening video file.")


# Invoke face detection, find largest cropping window and apply elliptical mask
def face_pass(framesGray, framesBGR):
    def crop_and_mask(frame, minX, minY, maxWidth, maxHeight, count):
        cropped_frame = frame[minY: minY + maxHeight, minX: minX + maxWidth]

        center = (int(maxWidth * 0.5), int(maxHeight * 0.5))
        axes = (int(maxWidth * 0.4), int(maxHeight * 0.5))

        mask = np.zeros_like(cropped_frame)
        cv2.ellipse(mask, center, axes, 0, 0, 360, (255, 255, 255), -1)

        return np.bitwise_and(cropped_frame, mask)

    def point_in_rect(point, rect):
        return \
            point["x"] > rect["minX"] and point["x"] < rect["minX"] + rect["maxWidth"] and \
            point["y"] > rect["minY"] and point["y"] < rect["minY"] + rect["maxHeight"]

    # Remember all faces, group faces that are within the same enclosing rectangle
    def remember_face(face, known_faces):
        (x, y, w, h) = face

        if len(known_faces) == 0:
            return [{
                    "minX" : x,
                    "minY" : y,
                    "maxWidth" : w,
                    "maxHeight" : h,
                    "count" : 0
                }]
        else:
            center_point = {
                "x" : x + w / 2 ,
                "y" : y + h / 2
            }
            head, tail = known_faces[0], known_faces[1:]
            if point_in_rect(center_point, head):
                return [{
                        "minX" : min(head["minX"], x),
                        "minY" : min(head["minY"], y),
                        "maxWidth" : max(head["maxWidth"], w),
                        "maxHeight" : max(head["maxHeight"], h),
                        "count" : head["count"] + 1
                    }] + tail
            else:
                return [head] + remember_face(face, tail)


    known_faces = []
    for i, frame in enumerate(framesGray):

        # only do face detection every 10 frames to save processing power
        if i % 10 <> 0:
            continue

        # Find all faces
        for face in detect_face(frame):
            known_faces = remember_face(face, known_faces)


    most_significant_face = max(known_faces, key=lambda x: x["count"])
    return (
        map(lambda f: crop_and_mask(f, **most_significant_face), framesGray),
        map(lambda f: crop_and_mask(f, **most_significant_face), framesBGR)
    )


def calculateFlow(frame1, frame2):
    flow = cv2.calcOpticalFlowFarneback(frame1, frame2, 0.5, 3, 15, 3, 2, 1.1, 0)
    horz = cv2.convertScaleAbs(flow[..., 0], None, 128 / SCALE_FLOW, 128)
    vert = cv2.convertScaleAbs(flow[..., 1], None, 128 / SCALE_FLOW, 128)
    return horz, vert


# Calculate the optical flow along the x and y axis
# always compares with the first image of the series
def flow_pass_static(framesGray):
    # TODO: might not be the flow we want, comparing only the first image to all others
    first = framesGray[0]
    flows = [calculateFlow(first, f) for f in framesGray]
    return [list(t) for t in zip(*flows)]


# Calculate the optical flow along the x and y axis
# always compares with the previous image in the series
def flow_pass_continuous(framesGray):
    flows = [calculateFlow(f1, f2) for f1, f2 in zip(framesGray[0] + framesGray, framesGray)]
    return [list(t) for t in zip(*flows)]


def save_to_disk(output_path, frames, name, max_frame_count=0):
    # only grab & compute every x-th frame or all if count == 0
    frame_count = len(frames)
    stride = 1
    if max_frame_count > 0:
        stride = frame_count / float(max_frame_count)

    relevant_frames = [int(i) for i in np.arange(0, frame_count, stride)]

    for i, frame in enumerate(frames):
        if not i in relevant_frames: continue
        cv2.imwrite(os.path.join(output_path, "%s_%s.png" % (name, i)), frame)


def main():
    if len(sys.argv) < 4:
        sys.exit("Usage: %s <max_frame_count> <path_to_video> <output_path>" % sys.argv[0])

    # read path to image as command argument
    max_frame_count = int(sys.argv[1])
    video_path = os.path.abspath(sys.argv[2])
    output_path = os.path.abspath(sys.argv[3])

    if not os.path.isfile(video_path):
        sys.exit("The specified <path_to_video> argument is not a valid filename")

    if not os.path.isdir(output_path):
        sys.exit("The specified <output_path> argument is not a valid directory")

    # ready to rumble
    framesGray, framesBGR = read_video(video_path)

    # 1. find faces 2. calc flow 3. save to disk
    croppedFramesGray, croppedFramesBGR = face_pass(framesGray, framesBGR)
    optical_flows = flow_pass_static(croppedFramesGray)

    static_flows = flow_pass_static(croppedFramesGray)
    # continous_flows = flow_pass_continuous(croppedFramesGray)

    save_to_disk(output_path, croppedFramesBGR, "frame-bgr", max_frame_count)
    save_to_disk(output_path, croppedFramesGray, "frame-gray", max_frame_count)
    save_to_disk(output_path, static_flows[0], "flow-x", max_frame_count)
    save_to_disk(output_path, static_flows[1], "flow-y", max_frame_count)

    # exit
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
