.global main
main:
	SET [ch], 72
	SET A, ch
	ADD A, 1
	SET [A], 101
	SET A, ch
	ADD A, 2
	SET [A], 108
	SET A, ch
	ADD A, 3
	SET [A], 111
	SET A, ch
	ADD A, 4
	SET [A], 0
	SET A, ch
	SET PUSH, A
	SET PUSH, 3
	SET PUSH, 0
	SET PUSH, A
	SET PUSH, 0
	JSR draw_line
	SUB SP, 4
	SET A, POP
	SET PC, POP
draw_line:
	SET A, [SP + 1]
	MUL A, 32
	ADD A, [video_ram]
	SET C, A
	SET A, [SP + 3]
	BOR A, [SP + 4]
	SET B, A
_blk2:
	SET A, [[SP + 2]]
	IFE A, 0
		SET PC, .blk4
_blk3:
	SET A, [[SP + 2]]
	BOR A, B
	SET [C], A
	SET A, [SP + 2]
	ADD A, 1
	SET [SP + 2], A
	SET PC, .blk2
_blk4:
	SET X, POP
	SET PC, POP
video_ram:
	.dw 32768
ch:
	.fill 5, 0
