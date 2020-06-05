.global main
main:
	JSR test
	SET PC, POP

.extern test
