
// we want main to be the first function
void main();

typedef short wchar_t;

static wchar_t* video_ram = (void*)0x8000;

static void draw_line(int line, wchar_t* string, int fgcol, int bgcol) {
    wchar_t* vram = video_ram + line * 32;
    int col = fgcol | bgcol;
    while (*string) {
        *vram = col | *string;
        string++;
    }
}

static wchar_t ch[5];

void main() {
    ch[0] = 'H';
    ch[1] = 'e';
    ch[2] = 'l';
    ch[3] = 'o';
    ch[4] = 0;
    draw_line(0, ch, 0, 3);
}

