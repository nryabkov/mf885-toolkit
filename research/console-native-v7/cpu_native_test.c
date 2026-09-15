#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "cpu.h"
static unsigned locked, reads, guards, changing, failed, badcfg;
static uint32_t tick;
uint32_t cpu_host_guard_enter(void){unsigned old=locked;locked=1;++guards;return old;}
void cpu_host_guard_leave(uint32_t saved){assert(locked);locked=saved;}
uint8_t cpu_mmio_read8(uint32_t a){assert(locked && a==0x12385u);return badcfg?0:1;}
uint32_t cpu_mmio_read32(uint32_t a){assert(locked);switch(a){case 0xd4080000u:return 4;case 0xd4080084u:return 2;case 0xd408005cu:case 0xd4080050u:case 0xd4080088u:return 0;default:assert(0);return 0;}}
static int counter(void *ctx,uint32_t *v){(void)ctx;assert(locked);++reads;if(failed)return 0;*v=tick+(changing?reads:0);return 1;}
static void snap(cpu_state *s,cpu_state *o,uint32_t t){tick=t;cpu_snapshot(s,counter,0,o);assert(!locked);}
int main(void){
 cpu_state s,o;char wire[CPU_WIRE_BYTES+1];cpu_init(&s);
 snap(&s,&o,100);assert(o.epoch==1 && o.flags==CPU_FLAG_WARMING);
 tick=120;cpu_idle_begin(&s,counter,0);assert(s.total_low==20 && s.idle_low==0);
 unsigned r=reads;cpu_idle_begin(&s,counter,0);assert(reads==r);
 snap(&s,&o,130);assert(o.total_low==30 && o.idle_low==10);
 tick=140;cpu_idle_end(&s,counter,0);assert(s.total_low==40 && s.idle_low==20);
 r=reads;cpu_idle_end(&s,counter,0);assert(reads==r);
 snap(&s,&o,180);assert(o.total_low==80 && o.idle_low==20 && o.epoch==1 && o.flags==CPU_FLAG_VALID);
 tick=200;cpu_idle_begin(&s,counter,0);tick=220;cpu_idle_end(&s,counter,0);
 snap(&s,&o,260);assert(o.total_low==160 && o.idle_low==40 && o.epoch==1 && o.transitions==4);
 memset(wire,'Z',sizeof wire);assert(cpu_serialize(&o,wire,CPU_WIRE_BYTES));assert(strlen(wire)==85 && wire[86]=='Z' && !strncmp(wire,"cpu2:01000000",13));
 assert(!cpu_serialize(&o,wire,CPU_WIRE_BYTES-1));
 changing=1;r=reads;snap(&s,&o,300);assert(reads-r==16 && o.flags==CPU_FLAG_UNAVAILABLE && !o.have_tick && !o.total_low);
 changing=0;snap(&s,&o,400);assert(o.epoch==2 && o.flags==CPU_FLAG_WARMING);snap(&s,&o,500);assert(o.total_low==100 && !o.idle_low);
 badcfg=1;r=reads;snap(&s,&o,600);assert(reads==r && o.flags==CPU_FLAG_UNAVAILABLE);badcfg=0;
 snap(&s,&o,0xfffffff0u);tick=0xfffffff8u;cpu_idle_begin(&s,counter,0);tick=8;cpu_idle_end(&s,counter,0);
 assert(s.total_low==24 && s.idle_low==16 && s.epoch==3);
 snap(&s,&o,4);assert(o.flags==CPU_FLAG_UNAVAILABLE && o.read_errors==3);
 snap(&s,&o,20);assert(o.epoch==4);
 s.total_low=0xfffffff0u;s.total_high=2;s.idle_low=0xfffffff8u;s.idle_high=1;s.open=1;
 snap(&s,&o,52);assert(o.total_low==16 && o.total_high==3 && o.idle_low==24 && o.idle_high==2);
 failed=1;snap(&s,&o,60);assert(o.flags==CPU_FLAG_UNAVAILABLE && !locked);failed=0;
 assert(guards>10);puts("CPU native core: busy/idle ratio, bounded reads, config failure, epoch recovery, wrap, carry, codec PASS");
}
