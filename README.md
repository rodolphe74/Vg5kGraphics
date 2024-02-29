# Vg5kGraphics
**_An [EF9345](https://en.wikipedia.org/wiki/Thomson_EF9345) Quest !_**

_(Or how to display full screen image on a [VG5000](https://en.wikipedia.org/wiki/Philips_VG5000))._

![Exotic](/images/exotic_parrot.png)

You like programming with constraints? You will love the following. 

The best you can do to display an image on this machine is to use the semi graphic quadrichromic mode which allows you to:
- redefine a maximum of 500 quadrichomic characters.
- a quadrichromic character can have 4 colors on a palette of 8 colors (white, cyan, magenta, blue, yellow, green, red, black).
- a quadrichromic character is defined by 10 slices of 4 px width (ie 4*10 px).
- each row contains 40 characters,
- for 25 rows,
- which allows a resolution of 160*250 px.

To create an image, you need to :
- crop the original image into rectangles of 4*10 px.
- create a quadrichromic character from them.
- tell the ef9345 to display each created character at the right place.

What's problematic is that 500 characters is not enough to cover the entire screen. 2 cases: 
- your image have a lot of characters in common, you need 500 or less characters -> OK, go for display
- your image have few characters in common, you need more than 500 characters -> you will have to pair look alike characters to lower characters count under 500. 
A kind of lossy compression.

# Guideline
## 1. Image reshaping
With a ratio of 0.64, the pixel in 160*250 are not square. It is necessary to transform the original image into someting which is squeezed in width:
```code
python resizeToVg5k.py .\gazoline.jpg
```
It will produce a well dimensionned image called "im_reframed.png" .
## 2. Image dithering
### Standard ordered dithering
### Yliluoma's ordered dithering
### Other methods ?

## 3. Transform image to Z80 assembly code

## 4. Compile assembly code to binary code

## 5. Launch binary code
