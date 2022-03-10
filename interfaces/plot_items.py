"""A class to allow selection of points to plot for a given antenna."""
import tkinter as tk


class PlotItems:
    """Create a dialog box that allows selection of an antenna and monitor points to plot."""
    def __init__(self, num_ants, mps):
        """Create a GUI for selecting monitor points to plot.

        Args:
            num_ants (int): Maximum number of antennas in selection.
            mps (:obj:'dict' of :obj:'str, :obj:'str'): Dictionary of monitor points to select from.
        """
        self.mp_list = []
        self.selected_ant = 1
        self.root = tk.Tk()
        self.separate_plots = False
        self.root.title("DSA-110 Monitor Points")

        # Define the section for allowing the user to choose the monitor points to plot
        # Set up the frame for entering choices
        entry_frame = tk.Frame(self.root)
        entry_frame.grid(column=0, row=0, sticky=tk.N, padx=20, pady=20)
        entry_frame.columnconfigure(0, minsize=10)
        entry_frame.columnconfigure(1, minsize=150)
        entry_frame.columnconfigure(2, minsize=130)

        # Create Tkinter variables to hold selected items
        self.tk_mp = tk.StringVar(self.root)
        self.tk_ant = tk.StringVar(self.root)

        # Monitor points are for a single antenna. This is the list to choose from.
        ants = []
        for i in range(1, num_ants):
            ants.append(f'ant{i}')
        len1 = 0
        len2 = 0
        for a in ants:
            len1 = max(len1, len(a))
        for m in mps:
            len2 = max(len2, len(m))

        # Create a spinner for antenna number with a label
        lab1 = tk.Label(entry_frame, text="Antenna")
        lab1.grid(row=0, column=0, sticky=tk.E)
        self.tk_ant = tk.Spinbox(entry_frame, from_=1, to=110)
        self.tk_ant.grid(row=0, column=1, sticky=tk.W+tk.E)

        # Create a drop-down list of monitor points with a label
        self.tk_mp.set(mps[0])  # Set the default option
        lab2 = tk.Label(entry_frame, text="Monitor point")
        lab2.grid(row=2, column=0, sticky=tk.E)
        dropdown2 = tk.OptionMenu(entry_frame, self.tk_mp, *mps)
        dropdown2.grid(row=2, column=1, sticky=tk.W+tk.E)
        dropdown2.configure(width=len2)

        # Add some buttons for actions
        add_button = tk.Button(entry_frame, text="--> Add -->", width=15,
                               command=self._add_callback)
        add_button.grid(row=0, column=2, rowspan=3, sticky=tk.E)
        delete_button = tk.Button(entry_frame, text="Delete <--", width=15,
                                  command=self._delete_callback)
        delete_button.grid(row=3, column=2, pady=15, sticky=tk.E)
        ok_button = tk.Button(entry_frame, text="OK", width=15, command=self._ok_callback)
        ok_button.grid(row=4, column=2, sticky=tk.E)
        quit_button = tk.Button(entry_frame, text="Quit", width=15, command=self._quit_callback)
        quit_button.grid(row=5, column=2, pady=5, sticky=tk.E)

        # Checkbox for single or multiple plots
        self.var1 = tk.IntVar()
        cb1 = tk.Checkbutton(entry_frame, text="Separate plots", variable=self.var1,
                             command=self._check)
        cb1.grid(row=3, column=1, sticky=tk.W)

        # Set up the frame for displaying choices
        width = len1 + len2 + 8
        display_frame = tk.Frame(self.root)
        display_frame.grid(column=1, row=0)
        display_frame.columnconfigure(0, pad=20)
        display_frame.columnconfigure(1, pad=20)
        display_frame.rowconfigure(0, pad=20)

        lab3 = tk.Label(display_frame, text="Monitor points to plot")
        lab3.grid(row=0, column=0)
        self.plot_items = tk.Text(display_frame, background='white', width=width, bd=3)
        self.plot_items.grid(row=1, column=0, padx=10, pady=20)
        self.root.mainloop()

    def _add_callback(self):
        new_mp = self.tk_mp.get()
        if new_mp not in self.mp_list:
            self.mp_list.append(new_mp)
            self.plot_items.insert(tk.END, f'{new_mp}\n')

    def _delete_callback(self):
        delete_index = self.plot_items.index(tk.INSERT)
        line, _ = delete_index.split('.')
        from_index = f'{line}.0'
        to_index = f'{line}.100'
        to_delete = self.plot_items.get(from_index, to_index)
        to_index = f'{int(line) + 1}.0'
        self.mp_list.remove(to_delete)
        self.plot_items.delete(from_index, to_index)

    def _ok_callback(self):
        self.selected_ant = int(self.tk_ant.get())
        self.root.destroy()

    def _quit_callback(self):
        self.mp_list = []
        self.root.destroy()

    def _check(self):
        if self.var1.get():
            self.separate_plots = True
