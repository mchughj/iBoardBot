
import cv2

f = "imgs/Cloud.png"

image = cv2.imread(f)

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
gray = cv2.bilateralFilter(gray, 11, 17, 17)
edged = cv2.Canny(gray, 30, 200)
contours, _ = cv2.findContours(edged, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

cv2.imshow("Original", image)
cv2.imshow("Gray", gray)
cv2.imshow("Edged", edged)

cv2.drawContours(image, contours, -1, (255,0,0),3)
cv2.imshow("OriginalWithContours", image)

cv2.waitKey(0)
