"""

kobwindow.py

Creates the main KOB window for MKOB and lays out its widgets
(controls).

"""

import tkinter as tk
import tkinter.ttk as ttk
import kobactions as ka
import kobconfig as kc

class KOBWindow:
    def __init__(self, root, VERSION):
        self.VERSION = VERSION
        ka.kw = self
        
        # window
        self.root = root
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        root.title(VERSION)

        # File menu
        menu = tk.Menu()
        root.config(menu=menu)
        fileMenu = tk.Menu(menu)
        menu.add_cascade(label='File', menu=fileMenu)
        fileMenu.add_command(label='New', command=ka.doFileNew)
        fileMenu.add_command(label='Open...', command=ka.doFileOpen)
        fileMenu.add_separator()
        fileMenu.add_command(label='Exit', command=ka.doFileExit)

        # Help menu
        helpMenu = tk.Menu(menu)
        menu.add_cascade(label='Help', menu=helpMenu)
        helpMenu.add_command(label='About', command=ka.doHelpAbout)

        # paned windows
        pwd1 = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        pwd1.grid(sticky=tk.N+tk.E+tk.S+tk.W, padx=6, pady=6)    
        pwd2 = ttk.PanedWindow(pwd1, orient=tk.VERTICAL)
        pwd1.add(pwd2, weight=2)

        # frames
        frm1 = tk.Frame(pwd2, padx=3, pady=0)
        frm1.rowconfigure(0, weight=1)
        frm1.columnconfigure(0, weight=2)
        pwd2.add(frm1, weight=1)

        frm2 = tk.Frame(pwd2, padx=3, pady=6)
        frm2.rowconfigure(0, weight=1)
        frm2.columnconfigure(0, weight=1)
        pwd2.add(frm2, weight=1)

        frm3 = tk.Frame(pwd1)
        frm3.rowconfigure(0, weight=1)
        frm3.columnconfigure(0, weight=1)
        pwd1.add(frm3, weight=1)

        frm4 = tk.Frame(frm3)
        frm4.columnconfigure(0, weight=1)
        frm4.grid(row=2)

        # reader
        self.txtReader = tk.Text(frm1, width=40, height=15, wrap=tk.WORD, bd=2,
                padx=2, pady=2,
                spacing1=0, spacing2=5, spacing3=0,
                font=('Helvetica', -14))
        self.txtReader.grid(row=0, column=0, sticky=tk.N+tk.E+tk.S+tk.W)
        scrlReader = tk.Scrollbar(frm1, command=self.txtReader.yview)
        scrlReader.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.txtReader['yscrollcommand'] = scrlReader.set

        # keyboard
        self.txtKeyboard = tk.Text(frm2, width=40, height=5, wrap=tk.WORD, bd=2,
                font=('Helvetica', -14))
        self.txtKeyboard.grid(row=0, column=0, sticky=tk.N+tk.E+tk.S+tk.W)
        scrlKeyboard = tk.Scrollbar(frm2, command=self.txtKeyboard.yview)
        scrlKeyboard.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.txtKeyboard['yscrollcommand'] = scrlKeyboard.set
        self.txtKeyboard.tag_config('highlight', underline=1)
        self.txtKeyboard.mark_set('mark', '0.0')
        self.txtKeyboard.mark_gravity('mark', tk.LEFT)
        self.txtKeyboard.tag_add('highlight', 'mark')
        
        # station list
        self.txtStnList = tk.Text(frm3, width=10, height=8, wrap=tk.NONE, bd=2,
                font=('Helvetica', -14))
        self.txtStnList.grid(row=0, column=0, sticky=tk.N+tk.E+tk.S+tk.W,
                padx=3, pady=0)
        scrlStnList = tk.Scrollbar(frm3, command=self.txtStnList.yview)
        scrlStnList.grid(row=0, column=1, sticky=tk.N+tk.S)
        self.txtStnList['yscrollcommand'] = scrlStnList.set

        # office ID
        self.varOfficeID = tk.StringVar()
        entOfficeID = tk.Entry(frm3, bd=2, font=('Helvetica', -14),
                textvariable=self.varOfficeID)
        entOfficeID.grid(row=1, column=0, sticky=tk.E+tk.W, padx=3, pady=6)

        # circuit closer / WPM
        lfm1 = tk.LabelFrame(frm4, padx=5, pady=5)
        lfm1.grid(row=0, column=0, columnspan=2, padx=3, pady=6)
        self.varCircuitCloser = tk.IntVar()
        chkCktClsr = tk.Checkbutton(lfm1, text='Circuit Closer',
                variable=self.varCircuitCloser)
        chkCktClsr.grid(row=0, column=0)
        tk.Label(lfm1, text='  WPM').grid(row=0, column=1)
        self.spnWPM = tk.Spinbox(lfm1, from_=5, to=40, justify=tk.CENTER,
                width=4, bd=2, command=ka.doWPM)
        self.spnWPM.bind('<Any-KeyRelease>', ka.doWPM)
        self.spnWPM.grid(row=0, column=2)

        # code sender
        lfm2 = tk.LabelFrame(frm4, text='Code Sender', padx=5, pady=5)
        lfm2.grid(row=1, column=0, padx=3, pady=6, sticky=tk.N+tk.E+tk.S+tk.W)
        self.varCodeSenderOn = tk.IntVar()
        chkCodeSenderOn = tk.Checkbutton(lfm2, text='On',
                variable=self.varCodeSenderOn)
        chkCodeSenderOn.grid(row=0, column=0, sticky=tk.W)
        self.varCodeSenderLoop = tk.IntVar()
        chkCodeSenderLoop = tk.Checkbutton(lfm2, text='Loop',
                variable=self.varCodeSenderLoop)
        chkCodeSenderLoop.grid(row=1, column=0, sticky=tk.W)

        # wire no. / connect
        lfm3 = tk.LabelFrame(frm4, text='Wire No.', padx=5, pady=5)
        lfm3.grid(row=1, column=1, padx=3, pady=6, sticky=tk.N+tk.S)
        self.varWireNo = tk.StringVar()
        self.spnWireNo = tk.Spinbox(lfm3, from_=1, to=32000, justify=tk.CENTER,
                width=7, bd=2, textvariable=self.varWireNo)
        self.spnWireNo.grid()
        self.cvsConnect = tk.Canvas(lfm3, width=6, height=10, bd=2,
                relief=tk.SUNKEN, bg='white')
        self.cvsConnect.grid(row=0, column=2)
        tk.Canvas(lfm3, width=1, height=2).grid(row=1, column=1)
        tk.Button(lfm3, text='Connect', command=ka.doConnect).grid(row=2,
                columnspan=3, ipady=2, sticky=tk.E+tk.W)

        # get configuration settings
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = kc.WindowSize
        x, y = kc.Position
        if x < 0:
            x = (sw - w) // 2
            y = (sh - h) // 2
        self.root.geometry('{}x{}+{}+{}'.format(w, h, x, y))
        self.varOfficeID.set(kc.OfficeID)
        self.varCircuitCloser.set(kc.CircuitCloser)
        self.spnWPM.delete(0)
        self.spnWPM.insert(tk.END, kc.WPM)
        ka.doWPM()
        self.varCodeSenderOn.set(kc.CodeSenderOn)
        self.varCodeSenderLoop.set(kc.CodeSenderLoop)
        self.varWireNo.set(kc.WireNo)

## TAKE CARE OF THESE
##    kw.txtStnList.insert('0.0', sl.getStationList())
    
##def start():
##    global running
##    running = True
##    runThread = threading.Thread(target=run)
##    runThread.daemon = True
##    runThread.start()
##
##def stop():
##    global running
##    running = False
##        
##def run():
##    s = '~  This is a test  +   '
##    while running:
##        for c in s:
##            if not running:
##                break
##            txtReader.insert(tk.END, c)
##            code = mySender.encode(c)
##            myKOB.sounder(code)
