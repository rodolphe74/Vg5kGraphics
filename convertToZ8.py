#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  quadri.py
#
#  Copyright 2020 rodoc <rodoc@linux.home>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

from PIL import Image
import os
import copy


BAYER_1 = ((170,),)
BAYER_2 = ((0, 170), (255, 85))
BAYER_3 = ((0, 223, 95), (191, 159, 63), (127, 31, 255))
BAYER_4 = ((0, 136, 34, 170), (204, 68, 238, 102), (51, 187, 17, 153),
		   (255, 119, 221, 85))

BAYER_8 = ((0, 194, 48, 242, 12, 206, 60,
			255), (129, 64, 178, 113, 141, 76, 190,
				   125), (32, 226, 16, 210, 44, 238, 28,
						  222), (161, 97, 145, 80, 174, 109, 157, 93),
		   (8, 202, 56, 250, 4, 198, 52,
			246), (137, 72, 186, 121, 133, 68, 182,
				   117), (40, 234, 24, 218, 36, 230, 20,
						  214), (170, 105, 153, 89, 165, 101, 149, 85))
						  
						  
BAYER_15x7 = ((2, 192, 43, 96, 70, 58, 128 ),
			  (106, 178, 132, 200, 183, 26, 219 ),
			  (75, 250, 101, 10, 156, 238, 168 ),
			  (161, 55, 29, 241, 120, 108, 19 ),
			  (130, 36, 207, 149, 65, 53, 214 ),
			  (87, 226, 152, 77, 224, 38, 202 ),
			  (63, 188, 113, 24, 185, 164, 144 ),
			  (236, 12, 84, 217, 125, 91, 5),
			  (137, 123, 248, 171, 14, 253, 197 ),
			  (180, 99, 67, 48, 212, 118, 72),
			  (41, 176, 221, 159, 135, 79, 51),
			  (243, 31, 22, 140, 46, 229, 190),
			  (115, 209, 166, 111, 103, 34, 154),
			  (94, 82, 147, 7, 245, 195, 17),
			  (233, 60, 231, 204, 89, 173, 142))


VG5K_COLORS = ((255,255,255), (0,255,255), (255,0,255), (0, 0, 255), 
				(255,255,0), (0,255,0), (255,0,0), (0,0,0))



START_ADR = """

org $5000
call main
ret

"""


ASM_LOADER = """

; Organisation memoire privee ef9345
	;===================================
	;|			EF9345					   VRAM	 8ko											|
	;|-----------------------------------------|   ~~ |-----------------------------------------|
	;|		   bloc 1	1024octets			   |   ~~ |			 bloc 8 1024octets				|
	;|-----------------------------------------|   ~~ |-----------------------------------------|
	;|TAMPON1|24octets| .....|TAMPON25|TAMPON26|   ~~ |TAMPON1|24octets| .....|TAMPON25|TAMPON26|
	;|$0000								  $0400|   ~~ |									   $2000|
	
	
	;|			   détail d'un BLOC de 1 Ko	 (1024 octets)					  |
	;|------------------------------------------------------------------------|
	;| TAMPON1	| TAMPON2  | TAMPON3  | TAMPON4	 | ~~ | TAMPON25  | TAMPON26  |
	;| Y=0		| Y=1	   | Y=8	  | Y=9		 | ~~ | Y=30	  | Y=31	  |
	;| 40 octets| 24 octets| 40 octets| 40 octets| ~~ |	 40 octets|	 40 octets|

	
	; Tampon : 1 2 3 4 5  6	 7	8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26
	;	   Y : 0 1 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31

	; Z=BLOC Y=TAMPON X=OCTET dans le TAMPON
	
	; exemple : octet 10 stocke dans le 3eme tampon du 2eme bloc :
	; Z=1 Y=8 X=09


	; Les registres utilises pour acceder a la memoire privee:
	; R4 et R5 : pointeur auxiliaires (X  Y	 Z )
	; R6 et R7 : pointeur principal	  (X' Y' Z')
	
	; X	 x5 x4 x3 x2 x1 x0		X'	x'5 x'4 x'3 x'2 x'1 x'0
	; Y		y4 y3 y2 y1 y0		X'		y'4 y'3 y'2 y'1 y'0
	; Z		   z3 z2 z1 z0		Z'			z'3 z'2 z'1 z'0
	
	; R4  -	   -	z'2	 y'4  y'3  y'2	y'1	 y'0
	; R5  z'0  z'1	x'5	 x'4  x'3  x'2	x'1	 x'0
	; R6  z3   z'3	 z2	  y4   y3	y2	 y1	  y0
	; R7  z0	z1	 x5	  x4   x3	x2	 x1	  x0


	; Ecriture memoire privee ef9345
	; ==============================
	; R0 = OCT Write R4/R5 00110100 = $34 = 52
	; R1 = Z = Valeur octet a ecrire = $03
	; R4 = Y = $09 -> tampon 9 = 3eme tampon (si num tampon commence a 0)
	; R5 = X = $C2 -> 3eme car du tampon (11 000010) = bloc 3 octet 2(=3)
	
	
	; Sinon c'est trop facile
	; =======================
	; Un tampon contient 4 car redefini (normal 40 octets)
	; Le tampon suivant le tampon 0 est le 8
	; Les tranches n de ces 4 cars sont successives:
	; Tranche 1 : OCT 1 2 3 4
	; Tranche 2 : OCT 1 2 3 4
	; ...
	; Tranche 10: OCT 1 2 3 4
	
	
	; Redef car
	; =========
	; R1 avec les 10 tranches en inc R5 de 4


	; Affichage
	; =========
	; R2 (B7 B6 B5 B4) : numero jeu -	B7 = 1 car non standard
	;					B6 = 0 monochrome
	;					B5, B4 = jeu a utiliser G'0(00/1), G'10(10), G'11(11)

	; R1 Numero car dans tampon Y :
	;					T0 :  0	   1	2	 3 
	;					T1 : 32	  33   34	35
	;					T2 : 36	  37   38	39
	;					...
	;					T25:124	 125  126  127


	; Jeu caracteres bichrome
	; =======================
	; G'0  = alphanumerique		(def bloc : DOR =		   B3 B2 B1 B0)
	; G'10 = semi graphique 1	(def bloc : DOR = B6 B5 B4			  )
	; G'11 = semi graphique 2


main:
	di
	push hl
	push ix
	
	
	; init mat pat...
	call init_redef_ef9345
	
	
	; redef des car sur 5 tampons en partant de q6
	ld de, {1} ; tampons
	call redef_cars
	
	; efface l ecran avec hl
	ld hl, $2a56	; avec des etoiles en magenta/cyan
	call efface_ecran


	; affichage aux dimensions
	ld de, {2}
	ld hl, sprite_use
	call display_sprite
	
	
	; attente espace
	ld a, 0
scrute:
	call 00AAh
	cp 32 ; a contient le code clavier
	jr nz, scrute


	call restore_ef9345
	
	; retour basic
	pop ix
	pop hl
	ei
	ret
	





;  ======================================
;  affichage direct du sprite
;  à partir de l'adresse "hl"
;  sur une dimension "de" (x*y)
;  suite de commande OCT en partant de hl
;  format lu :
;	  R1 R2 sur (x*y) octets
;	  soit 2 * d * e octets
;  name: display_sprite
;  @param hl  adresse de depart
;  @param de  dimension xy
;			  
;  @return
;  ======================================
display_sprite:
	push de
	push hl
	
	ld b, e
	ld a, 0
	ld (_i), a	; compteur de ligne

	
ligne_display_sprite:
	push b
	push d
	ld a, b
	ld (_buf), a
	ld b, d
	ld a, 0
	ld (_j), a	; compteur de col
	
colonne_display_sprite:
	; affichage des cars definis
	ld a, (hl)
	ld d, $21	; r1 = car (tampon b6 a b2 + octet b0 et b1)
	ld e, a		; tampon et car en (hl)
	call ef9345
	
	inc hl
	
	ld d, $22	; r2 = jeu
	ld e, (hl)	   ; ex bloc 6 11 101 0 01 (11 = quadri) (101 = 110 = 6, B0&B1 inverses) 
				;(01 HR + incrustation)
	call ef9345
	
	inc hl

	ld a, (_i)
	cp 0		; a = 0 ?
	jr z, zero_display_sprite
	add a, 7	; ajout de 7 seulement si pas 0
	zero_display_sprite:
	ld d, $26	; r6 = ligne (0 pour 0 et n+7 pour [1 <= n <= 24])
	ld e, a
	call ef9345

	ld d, $27	; r7 = colonne entre 0 et 39
	ld a, (_j)
	ld e, a
	inc a
	ld (_j), a
	call ef9345

	; initialise avant l appel donc inutile
	ld d, $23	; r3 = attributs couleurs quadri
	ld e, (hl)
	call ef9345
	
	inc hl

	ld d, $28	; d=40 (registre r0 + 8 pour l'execution) avec commande ligne suivante
	ld e, $00	; et e=0 krf dit a l'ef9345 d'executer les registres definis plus tot
	call ef9345
	
	djnz colonne_display_sprite
	
	; inc ligne
	ld a, (_i)
	inc a
	ld (_i), a
	
	pop d
	pop b
	djnz ligne_display_sprite
	
	pop hl
	pop de
	ret





;  ======================================
;  redefinition des cars ef9345
;  suite de commande OCT en partant du
;  label sprite_def
;  format lu :
;	  pour chaque tampon 
;	  R4 R5 et 4 cars entrelaces
;	  soit 42 octets
;  name: redef_cars
;  @param de  nombre de tampons de 4 cars
;			  a lire
;  @return
;  ======================================
redef_cars:
	push de
	push hl
	
	;~ ld b, 54 ; 54 tampons
	ld b, e ; nombre de tampons
	ld hl, sprite_def ; index R4-R5-tranches
	
loop_tampon:
	push b
	
	ld b, 40; 40 valeurs pour 8 car dans un tampon

	ld a, (hl) ; R4 - bit 3 Bloc (1 car 6=110 ou 7=111)	 - Tampon sur 5 bits
	ld (r4), a ; sauvegarde de l'accumulateur
	
	inc hl ; pointeur sur R5
	
	ld a, (hl) ; R5 bit 0 et 1 Bloc à l'envers (01 ou 11) - N° octet sur 6 bits
	ld (r5), a ; sauvegarde de l'accumulateur
	
	inc hl ; pointeur sur valeurs slice
	
loop_tranche:
	push af
	ld d, $21 ; r1
	ld e, (hl) ; Valeur a l index tranche 
	call ef9345
	
	ld d, $24 ; r4
	ld a, (r4)
	ld e, a ; 001 11111 = bloc B2  + N° tampon (31 = 24+7)
	call ef9345
	
	ld d, $25 ; r5
	ld a, (r5) ; bloc B0 B1 = 01
	ld e, a
	call ef9345

	ld d, $28 ; d=40 (registre r0 + 8 pour l'execution) avec commande ligne suivante
	ld e, $34 ; commande OCT
	call ef9345
	pop af
	
	inc a ; valeur r5 suivante (octet suivant dans le tampon)
	ld (r5), a ; on le garde au chaud
	inc hl ; index sur la valeur de la tranche suivante
	
	djnz loop_tranche
	
	pop b
	djnz loop_tampon
	
	pop hl
	pop de
	ret




;  ======================================
;  ecriture ef9345
;  name: ef9345
;  @param d numero registre ef9345
;  @param e valeur du registre
;  @return
;  ======================================
ef9345:
	call $0286; teste si ef935 est pret
	call $0d7c; ecrit dans ef9345 (d=numero du registre, e=valeur du registre)
	ret





;  ======================================
;  initialisation ef9345 commande longue
;  avec redefinition
;  name: init_ef9345
;  @param 
;  @return 
;  ======================================
init_redef_ef9345:

	; ROR
	ld d, $21 ; dans r1
	ld e, $08 ; 
	call ef9345
	ld d, $28 ; r0 exec
	ld e, $87 ; commande indirection r=1-> ror write
	call ef9345; ecrire dans le registre ror


	; DOR : definition adresses car redef 
	;			G'0 (B3 B2 B1 B0) = 0011
	;			G'10 g'11 (B6 B5 B4) = 010
	ld d, $21 ; dans r1
	ld e, $03 ; Quadri Q4 Q5 Q6 Q7
	call ef9345
	ld d, $28 ; r0 exec
	ld e, $84 ; commande indirection r=1-> dor write
	call ef9345; ecrire dans le registre dor

	; TGS
	ld d, $21 ; dans r1
	;ld e, $10 ; Alice
	ld e, $00 ; VG (625l et synchro)
	call ef9345
	ld d, $28 ; r0 exec
	ld e, $81 ; commande indirection r=1-> tgs write
	call ef9345; ecrire dans le registre tgs (commandes longues)

	; PAT
	ld d, $21 ; dans r1
	; ld e, $67 ; 0100 0111 Alice
	ld e, $77 ; VG (0111 0111 insertion video inhibe)
	call ef9345
	ld d, $28 ; r0 exec
	ld e, $83 ; commande indirection r=3 -> pat write
	call ef9345; ecrire dans le registre pat

	; MAT
	ld d, $21 ; dans r1
	ld e, $2e ; 0 1 01 110 (dh, curs, type curs, marge) 
	call ef9345
	ld d, $28 ; r0 exec avec valeur de e ligne suivante
	ld e, $82 ; commande indirection (1000 0 010) r=2 -> mat write
	call ef9345; ecrire dans le registre mat
	
	; ATTR
	;~ ld d, $22 ; r2
	;~ ld e, $81 ; attributs jeu de car / att video std
	;~ call ef9345

	;~ ld d, $23 ; r3
	;~ ld e, $71 ; blanc/rouge dans r3 01110001 -> bits de poids fort = 7
	;~ call ef9345	  
	ret





;  ======================================
;  remise ef9345 etat vg5000
;  name: restore_ef9345
;  @param 
;  @return 
;  ======================================	
restore_ef9345:
	ld d, $21 ; dans r1
	ld e, $00 ; 0000 0001
	call ef9345
	ld d, $28 ; r0 exec
	ld e, $81 ; commande indirection r=1-> tgs write
	call ef9345; ecrire dans le registre tgs (commandes longues)

	ld d, $21 ; dans r1
	ld e, $f7 ; 0100 0111
	call ef9345
	ld d, $28 ; r0 exec
	ld e, $83 ; commande indirection r=3 -> pat write
	call ef9345; ecrire dans le registre pat

	ld d, $21 ; dans r1
	ld e, $6e ; bleu
	call ef9345
	ld d, $28 ; r0 exec avec valeur de e ligne suivante
	ld e, $82 ; commande indirection (1000 0 010) r=2 -> mat write
	call ef9345; ecrire dans le registre mat
	ret



;  ======================================
;  efface l ecran
;  name: efface_ecran
;  @param h car a utiliser
;  @param l couleur encre/fond
;  @return 
;  ======================================	
efface_ecran:
	push de
	push bc
	push hl
	ld d, $22 ; R2
	ld e, $01; Attributs jeu de car / att video
	call ef9345
	ld d, $23 ; R3
	ld e, l ; Attributs jeu de car / att video
	call ef9345

	ld d, 20h		;krf (01) avec increment pointer
	ld e, 1			;r0
	call ef9345		;01 dans r0
	ld d, 21h

	ld a, h			; car a utiliser - ex 32 espace
	ld e, a			;car dans r1
	call ef9345		;r1
	ld h, 0			;ligne 0
	call eralin
	ld h, 08h		;seconde ligne=8
	ld b, 18h		;18h lignes
	
cls:
	push bc
	call eralin
	inc h
	pop bc
	djnz cls
	pop hl
	pop de
	pop bc
	ret

eralin:
	ld d, 27h	;r7
	ld e, 0		;clr r7 - colonne 0
	call ef9345 ;0 dans r7
	ld b, 28h	;nombre colonnes
	ld d, 38+8	; 38d=26h=100110 (r6 ligne)
	ld e,h		;h contient la ligne a effacer
	
erali1:
	call ef9345
	djnz erali1		;40x (28h dans b)
	ret






;  Variables globales
._buf
	db $00

.r4
	db $00

.r5 
	db $00

._i
	db $00
	
._j
	db $00

"""



def threshold_bayer_matrix(bayer_matrix, strength):
	mat = []
	for i in range(0, len(bayer_matrix)):
		row = []
		for j in range(0, len(bayer_matrix[i])):
			row.append(int(bayer_matrix[i][j] * strength))
		mat.append(tuple(row))
	return tuple(mat)





def find_closest_color(c, palette):
	diff = 100000
	closest = 0
	for i in range(0, len(palette)-1, 3):
		d = abs(c[0] - palette[i]) + abs(c[1] - palette[i+1]) + abs(c[2] - palette[i+2])
		if d < diff:
			diff = d
			closest = i
	return closest//3
	

def get_palette_data_from_string(palette_string):
	palette_data = []
	for i in range(len(palette_string) - 1, -1, -1):
		if palette_string[i] == '1':
			vg_color = VG5K_COLORS[i]
			# ~ print("vg_color", vg_color)
			for j in range(0,3):
				palette_data.append(vg_color[j])
	# ~ print("palette_data", palette_data)
	return palette_data

def find_index(c_rgb, full_palette):
	for i in range(0, len(full_palette)):
		if c_rgb[0] == full_palette[i][0] and c_rgb[1] == full_palette[i][1] and c_rgb[2] == full_palette[i][2]:
			# print(i, c_rgb[0], c_rgb[1], c_rgb[2])
			return i
	return 0
		
	

def find_closest_palette(car, car_rgb, full_palette):
	pixels = car.load()
	pixels_rgb = car_rgb.load()
	count_index = [0]*8
	palette_restriction = []
	for x in range(car.width):
		for y in range(car.height):
			c = pixels[x, y]
			c_rgb = pixels_rgb[x, y]
			idx = find_index(c_rgb, full_palette)
			# print(idx, c)
			count_index[idx] += 1
			# count_index[c] += 1
	# ~ print(count_index)
	for i in range(0, 4):
		max_count = count_index.index(max(count_index))
		palette_restriction.append(max_count)
		count_index[max_count] = -1
	# ~ print("p", palette_restriction)
	p = list("00000000")
	for i in range(len(palette_restriction)):
		p[palette_restriction[i]] = '1'
	palette_string = "".join(p)
	# ~ print(palette_string)
	return palette_string
	
	
def linear_space(x):
	x = x / 255
	if x <= 0.04045:
		y = x / 12.92
	else:
		y = ((x+0.055) / 1.055)**2.4
	return int(round(y * 255))


def car_key_to_list(car_key):
	l = car_key[1:].split('$')
	rl = []
	for v in l:
		rl.append('$' + v)
	return rl


def ordered_dither(im, bayer, palette):
	palette_data = []
	print(";palette size", len(palette))
	for i in range(0, len(palette)):
		for j in range(0, 3):
			color = palette[i]
			palette_data.append(color[j])
			
	dithered_color = [0, 0, 0]
	img = Image.new('P', (im.width, im.height))
	img.putpalette(palette_data * 32)
	pixels = im.load()
	for x in range(im.width):
		for y in range(im.height):
			c = pixels[x, y]
			if bayer is not None:
				map_value = bayer[y % len(bayer)][x % len(bayer[0])]
				dithered_color[0]  = linear_space(c[0]) + (map_value - 127)
				dithered_color[1]  = linear_space(c[1]) + (map_value - 127)
				dithered_color[2]  = linear_space(c[2]) + (map_value - 127)
				index = find_closest_color(dithered_color, palette_data)
			else:
				# pas de dithering
				index = find_closest_color(c, palette_data)
			img.putpixel((x,y), index)
	return img


def get_car_string(car):
	pixels = car.load()
	data = ""
	for y in range(0, 10):
		w1 = 0
		w2 = 0
		sl = ""
		for x in range(0, 4):
			c = pixels[x, y]
			b = '{0:02b}'.format(c)
			b = b[::-1] 
			sl = sl + b
		line = hex(int(sl, 2))
		line = "$" + line[2:]
		data += line + ","
	return data[0:len(data)-1]
	
	
def get_car_list(car, car_rgb, palette_string, full_palette):
	pixels = car.load()
	pixels_rgb = car_rgb.load()
	data = []
	for y in range(0, 10):
		w1 = 0
		w2 = 0
		sl = ""
		for x in range(0, 4):
			c = pixels[x, y]
			c_rgb = pixels_rgb[x, y]
			idx = find_index(c_rgb, full_palette)
			palette_data = get_palette_data_from_string(palette_string)
			# index = find_closest_color(VG5K_COLORS[c], palette_data)
			index = find_closest_color(VG5K_COLORS[idx], palette_data)
			b = '{0:02b}'.format(index)
			sl = b + sl
		line = hex(int(sl, 2))
		line = "$" + line[2:]
		data.append(line)
	return data


def get_palette():
	palette = []
	for i in range(len(VG5K_COLORS)):
		palette.append(VG5K_COLORS[i])
	return palette


def main(args):
	if len(sys.argv) <= 1:
		print("")
		print("I need the following arguments:")
		print("	 * a picture filename")
		print("")
		exit()

	# C est parti...
	
	print(START_ADR)
	full_palette = get_palette()


	print(";Converting " + sys.argv[1])
	im = Image.open(sys.argv[1])

	im_rgb = im.convert('RGB')

	width, height = im.size
	
	if width % 4 != 0:
		print("x width must be a 4 divisor")
		exit()
		
	if height % 10 != 0:
		print("y height must be a 10 divisor")
		exit()
	
	x_step_count = int(width / 4)
	y_step_count = int(height / 10)
	
	list_cars = []
	for y in range(0, y_step_count):
		for x in range(0, x_step_count):
			crop_tuple = (x * 4, y * 10, (x + 1) * 4, (y + 1) * 10)
			car = im.crop(crop_tuple)
			car_rgb = im_rgb.crop(crop_tuple)
			palette = find_closest_palette(car, car_rgb, full_palette)
			data = get_car_list(car, car_rgb, palette, full_palette)
			list_cars.append((data, palette))
	
	print(";cars count:", len(list_cars))

	# création dictionnaire par car
	print(";compressing")
	dic_by_car = {}
	for i in range(0, len(list_cars)):
		car = list_cars[i][0]
		car_string = "".join(car)
		if car_string in dic_by_car:
			dic_by_car[car_string].append(i)
		else:
			dic_by_car[car_string] = []
			dic_by_car[car_string].append(i)
		

	print(";dictionary size:", len(dic_by_car));
	print(";ratio", len(dic_by_car), "/",  len(list_cars))
	
	
	
	# grouping mode
	while len(dic_by_car) > 500:
		diff_max = 10000000
		i_found = 0
		j_found = 0
		for i in dic_by_car:
			for j in dic_by_car:
				if i != j:
					s1 = 0
					s2 = 0
					l1 = i[1:].split('$')
					l2 = j[1:].split('$')
					
					current_diff = 0
					for k in range(0, len(l1)):
						c1 = l1[k]
						c2 = l2[k]
						current_diff += abs(int(c1, 16) - int(c2, 16))
					# print(current_diff)
					if current_diff < diff_max:
						diff_max = current_diff
						i_found = i
						j_found = j
		print("; grouping ", i_found, j_found, " - difference", diff_max, " - dictionary size ", len(dic_by_car), flush=True)
		i_list = dic_by_car[i_found]
		j_list = dic_by_car[j_found]
		i_list.extend(j_list)
		del dic_by_car[j_found]
		dic_by_car[i_found] = i_list
	# fin grouping mode
	
	print(";dictionary size:", len(dic_by_car));
	
	
	if len(dic_by_car) > 500:
		print("Ca depasse")
		exit()
	
	# inversion du dictionnaire pour avoir la clé par position
	dic_by_pos = {}
	for i in dic_by_car:
		for j in dic_by_car[i]:
			dic_by_pos[j] = i
	
	
	
	
	print()
	print()
	print(".sprite_def")
	
	# count = 0
	count_bloc = 3
	count_tampon = 0
	count_octet = 0
	count_octet_du_tampon = 0
	total_tampon = 0

	list_dic = []
	dic_index = {}
	for car in dic_by_car:
		list_dic.append(car)
	
	

	
	for i in range(0, len(list_dic), 4):
		try:
			car_1 = car_key_to_list(list_dic[i])
			dic_index[list_dic[i]] = (count_bloc, count_tampon, count_octet_du_tampon)
		except IndexError as e:
			car_1 = ["$0","$0","$0","$0","$0","$0","$0","$0","$0","$0"]
			palette_1 = "00000000"
		
		try:
			car_2 = car_key_to_list(list_dic[i+1])
			dic_index[list_dic[i+1]] = (count_bloc, count_tampon, count_octet_du_tampon + 1)
		except IndexError as e:
			car_2 = ["$0","$0","$0","$0","$0","$0","$0","$0","$0","$0"]
			palette_2 = "00000000"
		
		try:
			car_3 = car_key_to_list(list_dic[i+2])
			dic_index[list_dic[i+2]] = (count_bloc, count_tampon, count_octet_du_tampon + 2)
		except IndexError as e:
			car_3 = ["$0","$0","$0","$0","$0","$0","$0","$0","$0","$0"]
			palette_3 = "00000000"
		
		try:
			car_4 = car_key_to_list(list_dic[i+3])
			dic_index[list_dic[i+3]] = (count_bloc, count_tampon, count_octet_du_tampon + 3)
		except IndexError as e:
			car_4 = ["$0","$0","$0","$0","$0","$0","$0","$0","$0","$0"]
			palette_4 = "00000000"
			
		print("; Bloc", count_bloc, "  -  Tampon ", count_tampon, " - Octet", count_octet_du_tampon)
		print("; car 1 : ", car_1)
		print("; car 2 : ", car_2)
		print("; car 3 : ", car_3)
		print("; car 4 : ", car_4)
		
		count_octet_du_tampon += 4
		
		# calcul R4 et R5 en fct Bloc/Tampon/Octet
		# R4 bit 3 Bloc (1 car 6=110 ou 7=111)	- Tampon sur 5 bits
		# R5 bit 0 et 1 Bloc à l'envers (00 10 01 ou 11) - N° octet sur 6 bits
		R4_bits = "001" + '{0:05b}'.format(count_tampon)
		R5_bits = ""
		if count_bloc == 3:
			# cas particulier Q3 pour R4
			R4_bits = "000" + '{0:05b}'.format(count_tampon)
			R5_bits = "11" + '{0:06b}'.format(count_octet)
		elif count_bloc == 4:
			R5_bits = "00" + '{0:06b}'.format(count_octet)
		elif count_bloc == 5:
			R5_bits = "10" + '{0:06b}'.format(count_octet)
		elif count_bloc == 6:
			R5_bits = "01" + '{0:06b}'.format(count_octet)
		elif count_bloc == 7:
			R5_bits = "11" + '{0:06b}'.format(count_octet)
		else:
			# ca depasse
			print("; Blocs limited to 7")
			exit()
		
		R4_hex = "$" + hex(int(R4_bits, 2))[2:]
		R5_hex = "$" + hex(int(R5_bits, 2))[2:]
		print ("; R4 (write) = ", R4_bits, "=", R4_hex)
		print ("; R5 (write) = ", R5_bits, "=", R5_hex)
		print ("	db ", R4_hex, ",", R5_hex)
		
			
		for j in range(0, 10):
			print("	   db ", car_1[j], ",", car_2[j], ",", car_3[j], ",", car_4[j])
		
		print(";;;;;;;")
		
		count_tampon += 1
		total_tampon += 1
		if count_tampon == 1:
			count_tampon += 7
		if count_tampon == 8:
			count_octet_du_tampon = 32
		if count_tampon == 32:
			count_tampon = 0
			count_octet_du_tampon = 0
			count_bloc += 1
		




	# Calcul de R1 et R2 pour l'utilisation des sprites
	print()
	print()
	print(".sprite_use")
	count_bloc = 3
	count_tampon = 0
	count_octet = 0
	count_col = 0
	count_lin = 0
	# total_tampon = 0
	for i in range(0, len(list_cars), 4):
		for j in range (0, 4):
			
			# recherche du caractere
			try:
				# car = list_cars[i+j][0]
				palette = list_cars[i+j][1]
				car_string = dic_by_pos[i+j]
				# print(car_string)
				indexes = dic_index[car_string]
				# print("found", i+j , car_string, indexes)
				count_bloc = indexes[0]
				count_tampon = indexes[1]
				count_octet = indexes[2]
				
			except IndexError as e:
				car = ["$0","$0","$0","$0","$0"]
				palette = "00000000"
				
			
			# calcul coordonnées
			if count_col == x_step_count:
				count_col = 0
				count_lin += 1
				if count_lin == y_step_count:
					break
			
			
			# Calcul de R1 et R2 en fonction du Bloc/Tampon/Octet
			# R1 numero du car avec 0,1,2,3 pour Tampon 1 et 32,127 pour tampons suivants
			# R2 11 (quadri) - Bloc 6  ou 7 (avec inv b1 et b0) 101 ou 111 - 0 - HR 0 - incrust 1 
			# R2 : bit 1 (ou R) = 1 pour indiquer la basse resolution
			# R2 : bit 2 (ou K) = 0 ou 1 en fct 4 premiers et 4 derniers car du tampon
			R1_hex = "$" + hex(count_octet)[2:]
			
			R2_bits = ""
			if count_bloc == 3:
				R2_bits = "11011001"
			elif count_bloc == 4:
				R2_bits = "11100001"
			elif count_bloc == 5:
				R2_bits = "11110001"
			elif count_bloc == 6:
				R2_bits = "11101001"
			elif count_bloc == 7:
				R2_bits = "11111001"

		   
			R2_hex = "$" + hex(int(R2_bits, 2))[2:]
			R3_hex = "$" + hex(int(palette, 2))[2:]
			print(";;;;;;;")
			print("; ", i+j, "- Bloc", count_bloc, " - Tampon ", count_tampon, " - Octet ", count_octet, " - (", count_col, ",", count_lin,") - Palette", palette)
			print("	   db ", R1_hex, ",", R2_hex, ",", R3_hex)
			count_col += 1

			
	print (";;;;;;;;;;;")
	resolution = "$" + hex(x_step_count)[2:].zfill(2) + hex(y_step_count)[2:].zfill(2)
	print ("; resolution quadrichromesque", str(x_step_count) + "*4", str(y_step_count) + "*10", 
		"=", resolution)
	print ("; tampons", total_tampon);
	
	
	print(ASM_LOADER.replace("{1}", str(total_tampon)).replace("{2}", resolution))
	

if __name__ == '__main__':
	import sys
	sys.exit(main(sys.argv))
