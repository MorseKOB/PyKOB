"""

display module

Displays a string of characters on a telegram-like form on the screen. Does
a simplistic kind of word wrapping. Optionally inserts proportional spacing
in front of the displayed string (normally a single character).

"""

import os
import pygame

SCREENSIZE = None # use maximum screen size
FULLSCREEN = True # fullscreen or windowed
PAGEWIDTH = 850   # width of page (pixels)
PADDING = 50      # margins surrounding text within page
WORDWRAP = 20     # number of spaces before margin to trigger word wrap
FONTNAME = ''     # uses pygame default if named font not available
FONTSIZE = 28     # font height in pixels
LINEPADDING = 15  # extra space between lines
FORMSPACING = 10  # blank space between forms
FOREGROUND = (32, 32, 32)  # text color (RGB)
BACKGROUND = (240, 220, 130)  # form color (RGB)
BLACK = (0, 0, 0) # screen background
HEADER = None     # filename of image to put at top of new form

class Display:
    def __init__(self):
        pygame.display.init()
        pygame.font.init()
        if SCREENSIZE:
            self.screenSize = SCREENSIZE
        else:
            self.screenSize = pygame.display.list_modes()[0]
        self.screenWidth, self.screenHeight = self.screenSize
        fs = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode(self.screenSize, fs)
        pygame.mouse.set_visible(False)
        self.margin = int((self.screenWidth - PAGEWIDTH) / 2)
        fontPath = pygame.font.match_font(FONTNAME)
        self.font = pygame.font.Font(fontPath, FONTSIZE)
        self.spaceWidth = self.font.size(' ')[0]
        self.spaces = 0
        self.x, self.y = self.margin + PADDING, PADDING
        self.lineHeight = FONTSIZE + LINEPADDING
        if HEADER:
            self.header = pygame.image.load(HEADER).convert_alpha()
        else:
            self.header = None
        pygame.display.set_caption('MorseKOB')
        self.screen.fill(BACKGROUND, pygame.Rect(self.margin, 0,
                self.screenWidth - 2 * self.margin, self.screenHeight))
        pygame.display.flip()

    def show(self, s, spacing=0):
        if s == '\r' or s == '\n':
            self.newLine(FONTSIZE + LINEPADDING)
            return
        if s == ' ':
            self.spaces += 1
            return
        sp = (self.spaces + spacing) * self.spaceWidth
        self.spaces = 0
        text = self.font.render(s, True, FOREGROUND)
        if self.x + sp + text.get_width() > self.margin + PAGEWIDTH - PADDING:
            self.x = self.screenWidth
        if self.x + WORDWRAP * sp > self.margin + PAGEWIDTH - PADDING:
            sp = 0
            self.newLine(FONTSIZE + LINEPADDING)
        self.screen.blit(text, (self.x + sp, self.y))
        self.x += sp + text.get_width()
        self.lineHeight = text.get_height() + LINEPADDING
        pygame.display.flip()
        if s[-1] == '=':
            self.show('\n')

    def newLine(self, lineHeight):
        self.x = self.margin + PADDING
        self.y += self.lineHeight
        self.lineHeight = lineHeight
        dy = (self.y + lineHeight) - (self.screenHeight - PADDING)
        if dy > 0:
            self.screen.scroll(0, -dy)
            self.screen.fill(BACKGROUND, pygame.Rect(self.margin,
                    self.screenHeight - dy,
                    self.screenWidth - 2 * self.margin, dy))
            self.y -= dy
            pygame.display.flip()

    def newForm(self):
        self.screen.scroll(0, -FORMSPACING)
        self.screen.fill(BLACK, pygame.Rect(
                self.margin, self.screenHeight - FORMSPACING,
                self.screenWidth - 2 * self.margin, FORMSPACING))
        self.y = self.screenHeight + PADDING
        self.lineHeight = 0
        if self.header:
            self.newLine(self.header.get_height() + PADDING)
            self.screen.blit(self.header,
                    ((self.screenWidth - self.header.get_width()) / 2, self.y))
        self.x = self.screenWidth
        pygame.display.flip()
