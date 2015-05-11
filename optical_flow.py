from __future__ import generators
import cv2, os, sys
import numpy as np

CLASSIFIER_PATH = "/usr/local/Cellar/opencv/2.4.11/share/OpenCV/haarcascades/haarcascade_frontalface_default.xml"
faceCascade = cv2.CascadeClassifier(CLASSIFIER_PATH)


def list_files(dir):
    "walk a directory tree, using a generator"
    for f in sorted(os.listdir(dir)):
        fullpath = os.path.join(dir,f)
        yield fullpath

def detect_face(image):

    faces = faceCascade.detectMultiScale(
        image,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
        flags=cv2.cv.CV_HAAR_SCALE_IMAGE
    )

    # Only use first result
    return faces[0]

def preprocessMMI(image):

    # crop the image to 360x576
    return image[0:576, 360:720]

def face_pass(files):

    minX = minY = sys.maxint
    maxWidth = maxHeight = 0
    images = []

    # for file in files:
    cap = cv2.VideoCapture(files)
    while cap.isOpened():

        returnValue, img = cap.read()

        if not returnValue:
            break

        # special case MMI dataset
        image = preprocessMMI(img)

        # image = cv2.imread(file)
        (x, y, w, h) = detect_face(image)

        minX = min(minX, x)
        minY = min(minY, y)
        maxWidth = max(maxWidth, w)
        maxHeight = max(maxHeight, h)

        images.append(image)

    cap.release()

    for image in images:

        # crop image image to recognized face and apply elliptical mask
        cropped_image = image[minY : minY + maxHeight, minX : minX + maxWidth]

        center = (int(maxWidth  * 0.5), int(maxHeight * 0.5))
        axes = (int(maxWidth * 0.4), int(maxHeight * 0.5))

        mask = np.zeros_like(cropped_image)
        # (cropped_image, center, axes, angle, startAngle, endAngle, color[, thickness[, lineType[, shift]]])  None
        cv2.ellipse(mask, center, axes, 0, 0, 360, (255, 255, 255), -1)
        yield np.bitwise_and(cropped_image, mask)


def flow_pass(images):


    prev = images.next()
    hsv = np.zeros_like(prev)
    hsv[..., 1] = 255

    prev = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    cv2.equalizeHist(prev)

    for image in images:

        next = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        cv2.equalizeHist(next)

        # prev, next, pyr_scale, levels, winsize, iterations, poly_n, poly_sigma, flags[, flow]
        flow = cv2.calcOpticalFlowFarneback(prev, next,  0.5,  3,  15,  3,  2,  1.1,  0)

        cv2.imshow('flow x', flow[..., 0])
        cv2.imshow('flow y', flow[..., 1])
        cv2.imshow('image ', image)

        # Wait indefinitely for user input
        k = cv2.waitKey(0) & 0xff
        if k == 27:
            break
        elif k == ord('s'):
            cv2.imwrite('opticalfb.png', next)
            cv2.imwrite('opticalhsv.png', rgb )

        prev = next


    cv2.destroyAllWindows()


def main():

    if len(sys.argv) < 2:
        sys.exit("Usage: %s <path_to_video>" % sys.argv[0])

    # read path to image as command argument
    video_path = os.path.abspath(sys.argv[1])

    if not os.path.isfile(video_path):
        sys.exit("The specified argument is not a valid filename")

    # ready to rumble
    #image_files = list_files(video_path)
    images = face_pass(video_path)
    flow_pass(images)


if __name__ == "__main__":
    main()


