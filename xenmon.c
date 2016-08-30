/* 
Author: Ratish Maruthiyodan
Purpose: This progam runs on the Dom0 of Xen Virtualization platform.
Peridically collects VM resource usage stats and saves them on a MySQL DB
*/

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include <linux/kdev_t.h>
#include <xenstat.h>
#include <xenstore.h>
#include <math.h>
#include <my_global.h>
#include <mysql.h>

#define INSERT_CPUSTAT "INSERT INTO cpu_stat(time,name,vcpu,phycpu,pcent_usage) VALUES(?,?,?,?,?)"
#define INSERT_NETSTAT "INSERT INTO network_stat(time,name,vif,bridge,rx_kb_sec,tx_kb_sec) VALUES(?,?,?,?,?,?)"
#define INSERT_VBDSTAT "INSERT INTO vbd_stat(time,name,vbd,backend,rd_KB_sec,wr_KB_sec) VALUES(?,?,?,?,?,?)"
#define TIME_STR_LEN 21

typedef struct {
	int id;
	int num_vcpu;
	unsigned long long *vcpu_usec;
	int *phycpu;
	int *vbd_r;
	int *vbd_w;
	unsigned long long *vif_rx;
	unsigned long long *vif_tx;
	char **vbd_phy;
	char **vif_bridge;
	char *name;
	struct domain_prev *next;
}domain_prev;

/*
 * The struct domain_prev is used to store All the Guest VM's previous 
 * stats to compare with the current stats
 *  
 * In the structure, vbd_r & vbd_w  are in KB
 * && vif_rx and vif_tx -- are in Bytes
*/


//   Function prototypes


static void monitor(void);
static void new_dom_add(xenstat_domain *);
static void check_reorganise_domain(xenstat_domain **, int);
static void compare_vcpu_us(domain_prev *dom1, xenstat_domain *domain, int num) ;
static float pcentage_vcpu_usage(unsigned long long, unsigned long int);
static void add_vifs_stats(xenstat_domain *, domain_prev *);
static void add_vbd_stats(xenstat_domain *, domain_prev *);
static void add_vcpu_stats(xenstat_domain *, domain_prev *);
static void compare_vif_rx_tx(xenstat_domain *, domain_prev *);
static void compare_vbd_rw(xenstat_domain *, domain_prev *);
static void vif_bridge_map(domain_prev *);
static void vbd_phy_map(domain_prev *);
static void vcpu_phycpu_map(void);
static void mysql_db_conn_init(void);
static void mysql_db_conn_close(void);
static void read_config(void);

xenstat_handle *xhandle = NULL;
xenstat_node *prev_node = NULL;
xenstat_node *cur_node = NULL;

struct timeval curtime;
unsigned long int current_time_usec=0, pre_time_usec=0;


int prev_num_domains = 0, num_domains = 0, dom_count=0, debug=0 , row, store=0;
char ***data;
const int ROW_MAX=200;

domain_prev *dom_first, *dom_last;
long long prev_time;

// for DB connectivity and also variables for prepared statements
MYSQL *mysql;
MYSQL_STMT  *stmt_cpustat, *stmt_netstat, *stmt_vdbstat;
MYSQL_BIND  bind_cpustat[5] , bind_netstat[6], bind_vbdstat[6];

float pcentage=0;
char dom_name[50], bridgename[25], backendname[160];
int vcpuid=0, pcpuid=0 , vifid , vbdid, rd_kbyte_sec, wr_kbyte_sec , delay, interval;
unsigned long long rxkbyte_sec, txkbyte_sec;
unsigned long str_length, time_len, br_length, be_length;
char time_str[TIME_STR_LEN];
const char *TIME_STR_FORMAT = "%F %H:%M:%S";

char server[50] = "192.168.100.156";
char user[15]= "root";
char password[25] = "root123";
char database[15] = "xen_monitor";


// function definitions start here ...

static void add_vifs_stats(xenstat_domain *domain, domain_prev *dom1)
{
	int num_vifs,i;
	xenstat_network *network;
	
	num_vifs = xenstat_domain_num_networks(domain);
	dom1->vif_rx = malloc(sizeof(unsigned int)* num_vifs);
	dom1->vif_tx = malloc(sizeof(unsigned int)* num_vifs);
	
	for (i=0; i<num_vifs; i++)
	{
		network = xenstat_domain_network(domain,i);
		dom1->vif_rx[i] = xenstat_network_tbytes(network);
		dom1->vif_tx[i] = xenstat_network_rbytes(network);
	}	
}

static void add_vbd_stats(xenstat_domain *domain, domain_prev *dom1)
{
	int num_vbds,i;
	xenstat_vbd *vbd;
		
	num_vbds = xenstat_domain_num_vbds(domain);
	dom1->vbd_r = malloc(sizeof(unsigned int)* num_vbds);
	dom1->vbd_w = malloc(sizeof(unsigned int)* num_vbds);
	
	for ( i=0 ; i < num_vbds ; i++)
	{
		vbd = xenstat_domain_vbd(domain,i);
		dom1->vbd_r[i] = xenstat_vbd_rd_sects(vbd)/2;
		dom1->vbd_w[i] = xenstat_vbd_wr_sects(vbd)/2;
	// Divided by 2 since the values are otherwise in sectors.
	}
}

static void add_vcpu_stats(xenstat_domain *domain, domain_prev *dom1)
{
	int j=0,i=0;
	xenstat_vcpu *vcpu;
	
	dom1->num_vcpu  = xenstat_domain_num_vcpus(domain);	
	dom1->vcpu_usec = malloc(sizeof(unsigned long long)* dom1->num_vcpu);
	dom1->phycpu = malloc((sizeof(int) * dom1->num_vcpu));

	for (j=0 ; j < dom1->num_vcpu; j++)
	{
		vcpu = xenstat_domain_vcpu(domain,j);
		dom1->vcpu_usec[j] = xenstat_vcpu_ns(vcpu);		
	}
	
	j=0;
	for (i=1;i<=row;i++)
	{
			printf("\n Physical CPU: %s", data[i][3]);
		if (strcmp(data[i][0],dom1->name)==0)
		{  
			dom1->phycpu[j] = atoi(data[i][3]);
		
			j++;
		}				
	}
			

}

static void new_dom_add(xenstat_domain *domain)
{
	int j=0,i=0;
	domain_prev *dom1 ;	
	
	dom_count=dom_count+1;

	dom1 = (domain_prev *)malloc(sizeof(domain_prev));
	
	if(dom_last == NULL)
	{
		dom_last=dom1;
		dom_first=dom1;
	}
	else
	{	
		dom_last->next = dom1;
		dom_last = dom1;
	}
	
	dom1->id = xenstat_domain_id(domain);
	dom1->name = malloc(strlen(xenstat_domain_name(domain)) * sizeof(char));
	strcpy(dom1->name,xenstat_domain_name(domain));

	add_vcpu_stats(domain,dom1);
	add_vifs_stats(domain,dom1);
	add_vbd_stats(domain,dom1);
	if(dom1->id !=0)
	{
		vif_bridge_map(dom1);
		vbd_phy_map(dom1);
	}
	
	// Initializing an array that needs a one time initialization
	// The array stores vpu-phycpu mapping info
	if (dom_count==1)
	{
		data = malloc(ROW_MAX * sizeof(char **)) ;
		for(i = 0 ; i < ROW_MAX ; i++)
		{
			data[i] = malloc(8 * sizeof(char *)) ;
			for (j = 0 ; j < 8 ; j++)
			{
				data[i][j] = malloc (20 * sizeof(char));
			} 
		}
	}
	return;
}	

static void check_reorganise_domain(xenstat_domain **domains, int num_dom)
{
	domain_prev *dom1 , *tmp;
	int i=0, id;
	
	dom1 = dom_first;
	tmp = dom1;
	
	for (i = 0; i< num_dom; i++)
	{
		if (tmp==dom_last && dom_count !=1)
		{	if(debug==1)
				printf("\n\t Under re-organize domain fn and dom1 = NULL\n");
			new_dom_add(domains[i]);
			dom1 = dom_last;
		}
		if (tmp == dom_last && dom_count == 1)
		{
			new_dom_add(domains[i]);
			dom1 = dom_first;		
		}

		id = xenstat_domain_id(domains[i]);
		
		// checking if the domain info here is about an non-existing domain
		// if so, delete the domain info
		
		if (id != dom1->id)
		{
			while (id != dom1->id)
			{
				if (dom1 != dom_last) 
				{
					tmp->next = dom1->next;
					free(dom1);
					dom1 = tmp->next;
					dom_count = dom_count-1;
				}
				else
				{	
					free(dom1);
					dom_last = tmp;
					dom1 = tmp;
					break;
				}	
			}
		}
		
		tmp = dom1;
		if(dom1 != dom_last)
			dom1 = dom1->next;
			
		if(debug==1)
			printf("\n\t Under re_organize domain fnx\n");
	}

}

static float pcentage_vcpu_usage(unsigned long long used_usec, unsigned long int usec_time_diff)
{
	float pcentage=0;
	pcentage = ((float)((float)used_usec / (float)usec_time_diff) * 100.0);
	pcentage = ceilf(pcentage *100) / 100;
	return (pcentage);
	
}

static void compare_vcpu_us(domain_prev *dom1, xenstat_domain *domain, int num)
{
	int i=0,j=0;
	xenstat_vcpu *vcpu;
	unsigned long long used_usec;
	unsigned long int usec_time_diff=0;
	
	printf("\nDomain Name : %s", dom1->name);
	usec_time_diff = current_time_usec - pre_time_usec;
	
	j=0;
	for (i=1;i<=row;i++)
	{
		if (strcmp(data[i][0],dom1->name)==0)
		{
			dom1->phycpu[j] = atoi(data[i][3]);
			j++;
		}
	}	
	time_len = TIME_STR_LEN;
		
	for (i=0; i < num; i++)
	{
		vcpu = xenstat_domain_vcpu(domain,i);
		if (debug==1){
				printf("\n vCPU # : %d -   Prev Val : %lldns \t Cur Val : %lldns \n", i,dom1->vcpu_usec[i], xenstat_vcpu_ns(vcpu));
			}
			
		used_usec = (xenstat_vcpu_ns(vcpu)/1000) - dom1->vcpu_usec[i] ;		
		pcentage = pcentage_vcpu_usage(used_usec, usec_time_diff);
				
		if (debug==1){
				printf("used_usec : %lld , usec_time_diff : %lld \n", used_usec,usec_time_diff);
			}
				
		printf("\nvCPU # %d Phy CPU # %d :: Used  %.2f%%",i,dom1->phycpu[i],pcentage);
		
	// converting from nano sec to micro secs since we are storing previous info in micro seconds	
		dom1->vcpu_usec[i] = xenstat_vcpu_ns(vcpu)/1000;		
	
	// For the prepared statements	
		pcpuid = dom1->phycpu[i];		
		strncpy(dom_name, dom1->name, 50);
		str_length = strlen(dom1->name);
		vcpuid = i;
		if (store==1) 
		{
			if (mysql_stmt_execute(stmt_cpustat))
			{
				fprintf(stderr, " mysql_stmt_execute(), 1 failed\n");
				fprintf(stderr, " %s\n", mysql_stmt_error(stmt_cpustat));
				exit(0);
			}
		}
	}
	
/*
 * Unlike for other physical mappings, we are dynamically collecting phy cpu on every iteration, 
 * considering that the phy CPU TO vCPU mapping that could dynamically change, as done by the xen hypervisor
 * 
*/ 

}

static void compare_vbd_rw(xenstat_domain *domain , domain_prev *dom1)
{
	unsigned long long used_usec;
	unsigned long int usec_time_diff=0;
	int num_vbds,i , cur_rbytes, cur_wbytes;
	xenstat_vbd *vbd;

	num_vbds = xenstat_domain_num_vbds(domain);
	usec_time_diff = (current_time_usec - pre_time_usec)/1000000;
		
	for ( i=0 ; i < num_vbds ; i++)
	{
		vbd = xenstat_domain_vbd(domain,i);
		cur_rbytes = xenstat_vbd_rd_sects(vbd)/2;
		cur_wbytes = xenstat_vbd_wr_sects(vbd)/2;
		
		// DB storage
		strncpy(dom_name, dom1->name, 50);
		str_length = strlen(dom1->name);
		strncpy(backendname, dom1->vbd_phy[i],160);
		be_length = strlen(dom1->vbd_phy[i]);
		vbdid = i;
		rd_kbyte_sec = (cur_rbytes - dom1->vbd_r[i])/usec_time_diff;
		wr_kbyte_sec = (cur_wbytes - dom1->vbd_w[i])/usec_time_diff;
		if (store==1) 
		{
			if (mysql_stmt_execute(stmt_vdbstat))
			{
				fprintf(stderr, " mysql_stmt_execute(), 1 failed\n");
				fprintf(stderr, " %s\n", mysql_stmt_error(stmt_vdbstat));
				exit(0);
			}
		}
		printf("\n Backend: %s :: Read KB/s # %d , Write KB/s # %d", dom1->vbd_phy[i], (cur_rbytes - dom1->vbd_r[i])/usec_time_diff, (cur_wbytes - dom1->vbd_w[i])/usec_time_diff);
				
		dom1->vbd_r[i] = cur_rbytes;
		dom1->vbd_w[i] = cur_wbytes;
				
	}
}

static void compare_vif_rx_tx(xenstat_domain *domain , domain_prev *dom1)
{
	unsigned long long used_usec;
	unsigned long int usec_time_diff=0;
	unsigned long long cur_rx_bytes, cur_tx_bytes;
	int num_vifs,i;
	xenstat_network *network;

	num_vifs = xenstat_domain_num_networks(domain);
	usec_time_diff = (current_time_usec - pre_time_usec)/1000000;
		
	for ( i=0 ; i < num_vifs ; i++)
	{
		network = xenstat_domain_network(domain,i);
		cur_rx_bytes = xenstat_network_tbytes(network);
		cur_tx_bytes = xenstat_network_rbytes(network);
// DB storage
		strncpy(dom_name, dom1->name, 50);
		str_length = strlen(dom1->name);
		strncpy(bridgename, dom1->vif_bridge[i],20);
		br_length = strlen(bridgename);
		vifid = i;
		rxkbyte_sec = ((cur_rx_bytes - dom1->vif_rx[i])/usec_time_diff)/1000;
		txkbyte_sec = ((cur_tx_bytes - dom1->vif_tx[i])/usec_time_diff)/1000;
		if (store==1) 
		{		
			if (mysql_stmt_execute(stmt_netstat))
			{
				fprintf(stderr, " mysql_stmt_execute(), 1 failed\n");
				fprintf(stderr, " %s\n", mysql_stmt_error(stmt_netstat));
				exit(0);
			}
		}
		printf("\n VIF: %d :: Bridge: %s :: RX bytes/s # %lld , TX bytes/s # %lld",i, dom1->vif_bridge[i] ,(cur_rx_bytes - dom1->vif_rx[i])/usec_time_diff, (cur_tx_bytes - dom1->vif_tx[i])/usec_time_diff);
		//if (cur_rx_bytes - dom1->vif_rx[i])/usec_time_diff < 0)
			//printf("\n cur_rx_bytes = %lld ")
		dom1->vif_rx[i] = cur_rx_bytes;
		dom1->vif_tx[i] = cur_tx_bytes;

	}
}

static void vif_bridge_map(domain_prev *dom1)
{
	struct xs_handle *xs;
	xs_transaction_t th;
	char *path1, *path2, conv_domid[3];
	int i=0, j=0  ;
	unsigned int num_vifs, len;
	char **vifs,*bridge;

	path1 = (char *)malloc(100);
	path2 = (char *)malloc(100);


	xs = xs_open(XS_OPEN_READONLY);
	if ( xs == NULL ) printf("error with xs_open");
	
	th = xs_transaction_start(xs);	
	
	
	strcpy(path1,"/local/domain/");
	sprintf(conv_domid, "%d", dom1->id);
	strcat(path1,conv_domid);
	strcat(path1,"/device/vif");
	vifs = xs_directory(xs, th, path1, &num_vifs);
	dom1->vif_bridge = malloc(sizeof(char[20]));
		
		for (j=0;j<num_vifs;j++)
		{
			strcpy(path2,"/local/domain/0/backend/vif/");
			strcat(path2,conv_domid);
			strcat(path2,"/");
			strcat(path2,vifs[j]);
			strcat(path2,"/bridge");
			printf("\n PATH2 = %s",path2);
			
			bridge = xs_read(xs, th, path2, &len); 
			printf("\t\t%s\n",bridge);
			
			dom1->vif_bridge[j] = malloc(sizeof(strlen(bridge)));
			strcpy(dom1->vif_bridge[j],bridge); 
		}
	free(vifs);
	free(path1);
	free(path2);
	xs_transaction_end(xs, th, true);	
	xs_daemon_close(xs);
}

static void vbd_phy_map(domain_prev *dom1)
{
	struct xs_handle *xs;
	xs_transaction_t th;
	char *path1, *path2, conv_domid[3];
	int j=0;
	unsigned int num_vbds=0,len=0;
	char **vbds,*vdsk;

	xs = xs_open(XS_OPEN_READONLY);
	if ( xs == NULL ) printf("error with xs_open");
	
	path1 = (char *)malloc(40*sizeof(char));
	path2 = (char *)malloc(40*sizeof(char));
	th = xs_transaction_start(xs);
		
	strcpy(path1,"/local/domain/");
	
	sprintf(conv_domid, "%d", dom1->id);
	strcat(path1,conv_domid);

	strcat(path1,"/device/vbd");
	vbds = xs_directory(xs, th, path1, &num_vbds);
	
	dom1->vbd_phy = malloc(num_vbds * sizeof(char **));
	
	for (j=0 ; j<num_vbds; j++)
	{		
		strcpy(path2,"/local/domain/0/backend/vbd/");
		strcat(path2,conv_domid);
		strcat(path2,"/");
		strcat(path2,vbds[j]);
		strcat(path2,"/params");
		printf("\n PATH2 = %s",path2);
			
		vdsk = xs_read(xs, th, path2, &len); 
			
		printf("\t\t%s\n",vdsk);
		
		dom1->vbd_phy[j] = malloc(len * sizeof(char));
		strcpy(dom1->vbd_phy[j], vdsk);
	}
	free(path1);
	free(path2);
	
	xs_transaction_end(xs, th, true);
	
	xs_daemon_close(xs);
	free(vbds);
}


static void vcpu_phycpu_map(void)
{
/* This is mainly a string parsing function...
 * Objective is the derrive the info on Physical CPUs from the system commad : xm vcpu-list
 * And after selectively saving the output into a multi-diamentional array, store the 
 * resulting data into the domain_prev.
*/
	FILE *fpipe;
    char *command = "xm vcpu-list";
    char *line = malloc(8);
    int i=0, j=0, chr=0, element=0, pre_alpha=0;
    
    row = 0;
    
    if (0 == (fpipe = (FILE*)popen(command, "r")))
    {
        perror("popen() failed.");
        exit(1);
    }

    while (fread(line, 4, 1, fpipe))
    {
		
        j=0;
		while(line[j])
		{			
			if(line[j] != ' ' && line[j] != '\n' && line[j] != '=')
			{
				//printf(" %c",line[j]);
				 data[row][element][chr] = line[j];
				 chr++;
				 pre_alpha=1;
			}
			if (( line[j] == ' ' && pre_alpha==1 ) || line[j] == '\n' )
			{
				data[row][element][chr]='\0';
				chr=0;
				element++;
				if(element==8)
				{  
					row++;
					element=0;
				}
				pre_alpha=0;
				
			}
			j++;
		}
     }
     
    pclose(fpipe);

	if (debug==1) 
	{				
		for (i=0;i<=row;i++)
		{
			printf("\n\n Row: %d\n",i);
			for (j=0; j<8 ;j++)
				printf("%s\t",data[i][j]);
			//free(data[i][j]);
		}
	}
   
}

static void mysql_db_conn_init(void)
{
	
// MySQL connection init

	mysql = mysql_init(NULL);
	if (!mysql_real_connect(mysql, server, user, password, database, 0, NULL, 0)) {
		fprintf(stderr, "%s\n", mysql_error(mysql));
		exit(1);
	}
	
// MySQL vcpu stat
	stmt_cpustat = mysql_stmt_init(mysql);
	
	if (!stmt_cpustat)	{
		fprintf(stderr, " mysql_stmt_init(), out of memory\n");
		exit(0);
	}
	
	if (mysql_stmt_prepare(stmt_cpustat, INSERT_CPUSTAT, strlen(INSERT_CPUSTAT)))
	{
		fprintf(stderr, " mysql_stmt_prepare(), INSERT failed\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_cpustat));
		exit(0);
	}
		
// MySQL vbd stat		
	stmt_vdbstat = mysql_stmt_init(mysql);
	if (!stmt_vdbstat)
	{
		fprintf(stderr, " mysql_stmt_init(), out of memory\n");
		exit(0);
	}
	if (mysql_stmt_prepare(stmt_vdbstat, INSERT_VBDSTAT, strlen(INSERT_VBDSTAT)))
	{
		fprintf(stderr, " mysql_stmt_prepare(), INSERT failed\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_vdbstat));
		exit(0);
	}
		
// MySQL net stat
	stmt_netstat = mysql_stmt_init(mysql);
	if (!stmt_netstat)
	{
		fprintf(stderr, " mysql_stmt_init(), out of memory\n");
		exit(0);
	}
	if (mysql_stmt_prepare(stmt_netstat, INSERT_NETSTAT, strlen(INSERT_NETSTAT)))
	{
		fprintf(stderr, " mysql_stmt_prepare(), INSERT failed\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_netstat));
		exit(0);
	}		
	
	
	memset(bind_cpustat, 0, sizeof(bind_cpustat));
	memset(bind_netstat, 0, sizeof(bind_netstat));
	memset(bind_vbdstat, 0, sizeof(bind_vbdstat));
	
/*For prepared statements for table : cpu_stat
 */
	bind_cpustat[0].buffer_type= MYSQL_TYPE_STRING;
	bind_cpustat[0].buffer= (char *)time_str;
	bind_cpustat[0].buffer_length= 21;
	bind_cpustat[0].is_null= 0;
	bind_cpustat[0].length= &time_len;
	
	bind_cpustat[1].buffer_type= MYSQL_TYPE_STRING;
	bind_cpustat[1].buffer= (char *)dom_name;
	bind_cpustat[1].buffer_length= 50;
	bind_cpustat[1].is_null= 0;
	bind_cpustat[1].length= &str_length;
	
	bind_cpustat[2].buffer_type= MYSQL_TYPE_LONG;
	bind_cpustat[2].buffer= (int *)&vcpuid;
	bind_cpustat[2].is_null= 0;
	bind_cpustat[2].length= 0;
	
	bind_cpustat[3].buffer_type= MYSQL_TYPE_SHORT;
	bind_cpustat[3].buffer= (char *)&pcpuid;
	bind_cpustat[3].is_null= 0;
	bind_cpustat[3].length= 0;
			
	bind_cpustat[4].buffer_type= MYSQL_TYPE_FLOAT;
	bind_cpustat[4].buffer= (char *)&pcentage;
	bind_cpustat[4].is_null= 0;
	bind_cpustat[4].length= 0;
	
	if (mysql_stmt_bind_param(stmt_cpustat,bind_cpustat))
	{
		fprintf(stderr, " mysql_stmt_bind_param() failed\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_cpustat));
		exit(0);
	}

/* For prepared statements for table : network_stat
 */

	bind_netstat[0].buffer_type= MYSQL_TYPE_STRING;
	bind_netstat[0].buffer= (char *)time_str;
	bind_netstat[0].buffer_length= 21;
	bind_netstat[0].is_null= 0;
	bind_netstat[0].length= &time_len;
	
	bind_netstat[1].buffer_type= MYSQL_TYPE_STRING;
	bind_netstat[1].buffer= (char *)dom_name;
	bind_netstat[1].buffer_length= 50;
	bind_netstat[1].is_null= 0;
	bind_netstat[1].length= &str_length;
	
	bind_netstat[2].buffer_type= MYSQL_TYPE_LONG;
	bind_netstat[2].buffer= (int *)&vifid;
	bind_netstat[2].is_null= 0;
	bind_netstat[2].length= 0;
	
	bind_netstat[3].buffer_type= MYSQL_TYPE_STRING;
	bind_netstat[3].buffer= (char *)bridgename;
	bind_netstat[3].buffer_length=20;
	bind_netstat[3].is_null= 0;
	bind_netstat[3].length= &br_length;
			
	bind_netstat[4].buffer_type= MYSQL_TYPE_LONG;
	bind_netstat[4].buffer= (char *)&rxkbyte_sec;
	bind_netstat[4].is_null= 0;
	bind_netstat[4].length= 0;
	
	bind_netstat[5].buffer_type= MYSQL_TYPE_LONG;
	bind_netstat[5].buffer= (char *)&txkbyte_sec;
	bind_netstat[5].is_null= 0;
	bind_netstat[5].length= 0;
	
	if (mysql_stmt_bind_param(stmt_netstat, bind_netstat))
	{
		fprintf(stderr, " mysql_stmt_bind_param() failed\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_netstat));
		exit(0);
	}
	
/* For prepared statements for table : VBD_STAT
 */
	
	bind_vbdstat[0].buffer_type= MYSQL_TYPE_STRING;
	bind_vbdstat[0].buffer= (char *)time_str;
	bind_vbdstat[0].buffer_length= 21;
	bind_vbdstat[0].is_null= 0;
	bind_vbdstat[0].length= &time_len;
	
	bind_vbdstat[1].buffer_type= MYSQL_TYPE_STRING;
	bind_vbdstat[1].buffer= (char *)dom_name;
	bind_vbdstat[1].buffer_length= 50;
	bind_vbdstat[1].is_null= 0;
	bind_vbdstat[1].length= &str_length;
	
	bind_vbdstat[2].buffer_type= MYSQL_TYPE_LONG;
	bind_vbdstat[2].buffer= (int *)&vbdid;
	bind_vbdstat[2].is_null= 0;
	bind_vbdstat[2].length= 0;
	
	bind_vbdstat[3].buffer_type= MYSQL_TYPE_STRING;
	bind_vbdstat[3].buffer= (char *)backendname;
	bind_vbdstat[3].buffer_length=160;
	bind_vbdstat[3].is_null= 0;
	bind_vbdstat[3].length= &be_length;
			
	bind_vbdstat[4].buffer_type= MYSQL_TYPE_LONG;
	bind_vbdstat[4].buffer= (char *)&rd_kbyte_sec;
	bind_vbdstat[4].is_null= 0;
	bind_vbdstat[4].length= 0;
	
	bind_vbdstat[5].buffer_type= MYSQL_TYPE_LONG;
	bind_vbdstat[5].buffer= (char *)&wr_kbyte_sec;
	bind_vbdstat[5].is_null= 0;
	bind_vbdstat[5].length= 0;
	
	if (mysql_stmt_bind_param(stmt_vdbstat, bind_vbdstat))
	{
		fprintf(stderr, " mysql_stmt_bind_param() failed\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_vdbstat));
		exit(0);
	}

	
}

static void mysql_db_conn_close(void)
{	
	if (mysql_stmt_close(stmt_cpustat))
	{
		fprintf(stderr, " failed while closing the statement\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_cpustat));
		exit(0);
	}
	if (mysql_stmt_close(stmt_vdbstat))
	{
		fprintf(stderr, " failed while closing the statement\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_vdbstat));
		exit(0);
	}
	if (mysql_stmt_close(stmt_netstat))
	{
		fprintf(stderr, " failed while closing the statement\n");
		fprintf(stderr, " %s\n", mysql_stmt_error(stmt_netstat));
		exit(0);
	}	
	mysql_close(mysql);
}

static void monitor(void)
{	
	xenstat_domain **domains;
	static domain_prev *dom1, *tmp;
	xenstat_vcpu *vcpu;	
	unsigned int i, j,  num_vcpus = 0, extra;

	
/*
 * Time related functions
 */
	pre_time_usec = current_time_usec;	
	gettimeofday(&curtime, NULL);
	strftime(time_str, TIME_STR_LEN, TIME_STR_FORMAT, localtime(&curtime.tv_sec));
	printf("\nTime: %s", time_str);
	
	current_time_usec=curtime.tv_sec*1000000 + curtime.tv_usec;	
	
	if(debug==1)
		printf("\n\t Nano Secs: %f \t In Secs: %10llu\n", curtime.tv_usec, curtime.tv_sec);
		
/* 
 * End of Time collection part
 */


// -------- Get the Domain information ---------

	cur_node = xenstat_get_node(xhandle, XENSTAT_ALL);
	if (cur_node == NULL)
		printf("Failed to retrieve statistics from libxenstat\n");

	num_domains = xenstat_node_num_domains(cur_node);
	
	if(debug==1)
		printf("\nNumber of Guest VMs %d\n",num_domains);

/*
 * Need to check this in the future, to find a better alternative to allocating memory during every iteration.
 */ 
	domains = malloc(num_domains*sizeof(xenstat_domain *));
	if(domains == NULL)
		printf("Failed to allocate memory\n");
		
	dom1 = dom_first;
	
//For mysql DB Connection init , 
	mysql_db_conn_init();
		
	for (i=0; i < num_domains; i++) 
	{
		domains[i] = xenstat_node_domain_by_index(cur_node, i);
	}
	
	// Here we initialize the view about vCPU - PhyCPU.. can't find a better place
	if (dom_count != 0) vcpu_phycpu_map();	
/*
 * The main loop that repeats for the number of running Guest VMs
 */	
	for (i=0; i < num_domains; i++) 
	{  //  Can improve the below if condition .. hold on!  Till we confirm that everything else is in its place
		if(dom_count == 0 || (dom_count < num_domains && dom_count < i+1))
		{
			new_dom_add(domains[i]);
			dom1 = dom_last;
		}

		if (dom1->id != xenstat_domain_id(domains[i]))
		{	
			printf(" \n\t Calling Re-Organize : dom1->id = %d ,  domains[i]->id = %d \n", dom1->id , xenstat_domain_id(domains[i]) );
			check_reorganise_domain(domains,num_domains);
			break;
		}

		num_vcpus = xenstat_domain_num_vcpus(domains[i]);
		compare_vcpu_us(dom1, domains[i],num_vcpus);
		compare_vbd_rw(domains[i],dom1);
		compare_vif_rx_tx(domains[i],dom1);

		if(dom1 != dom_last)
			dom1 = dom1->next;
	 	printf("\n");
	 	
	}
	
	// Cleaning up stopped Domain info. from linked-list
	
	if (num_domains < dom_count)
	{
		dom1 = dom_first;
		tmp = dom1;
		for (i=1; i <= num_domains; i++)
		{
			tmp = dom1;
			dom1 = dom1->next;
		}
		dom_last = tmp;
		dom_last->next = NULL;
		
		extra = dom_count - num_domains;
		
		for (j=1;j <= extra; j++)
		{	if (j < extra )
				tmp=dom1->next;
				
			free(dom1);			
			dom1 = tmp;			
			dom_count = dom_count -1;
		}
	}
	free(domains);
	free(cur_node);
	mysql_db_conn_close();
	
}

static void read_config(void)
{
	FILE *fp;
	
	fp = fopen("xenmon.conf","r"); // read mode

	if( fp == NULL )
	{
		perror("Error while opening the config file: xenmon.conf, in the current directory ");
		exit(EXIT_FAILURE);
	}
	char line [50];
	int i = 0, j=0, value_started = 0 , c = 0, n=0, c1=0 ;
	char argument[10][50], parameter[10][50];
	
	while (fgets(line, sizeof(line), fp))
    {	
		value_started=0;
		c = 0;
		c1 = 0;
		printf("From conf file : %s",line);
		
		for (i=0;i<strlen(line);i++)
		{
			if (value_started == 1)				
			{	
				if (line[i] != ' ' && line[i] != '\n')
				{
					argument[j][c]=line[i];
					c = c+1;
				}
			}
			
			if (value_started == 0)
			{
				if (line[i] != ' ' && line[i] != '=')
				{
					parameter[j][c1] = line[i];
					c1 = c1 + 1;
				}	
			}
			
			if (line[i] == '=')
			{
				value_started=1;
				parameter[j][c1] = '\0';
			}	
		}
		argument[j][c] = '\0';
		j=j+1;		
	}


	for(n=0; n<j; n++)
	{	
		printf("Parameter = %s ", parameter[n]);
		printf("= %s\n", argument[n]);
		
		if (strcmp(parameter[n],"DB_ip")==0)
			strcpy(server,argument[n]);
			
		if (strcmp(parameter[n],"DB_name")==0)
			strcpy(database,argument[n]);
			
		if (strcmp(parameter[n],"DB_user")==0)
			strcpy(user,argument[n]);
			
		if (strcmp(parameter[n],"DB_password")==0)
			strcpy(password,argument[n]);
			
		if (strcmp(parameter[n],"Delay")==0)
			delay = atoi(argument[n]);
			
		if (strcmp(parameter[n],"Interval")==0)
			interval = atoi(argument[n]);
	}
	printf("\nserver: %s , database: %s, user: %s, password: %s, delay: %d, interval: %d", server,database,user,password,delay,interval);

	fclose(fp);
	
}

int main(int argc, char **argv)
{	
	// Turn on the debug only when required
	debug=0;
	xhandle = xenstat_init();
	if(xhandle == NULL) 
	{
		printf("Could not allocate xen handle");
	}
		
	read_config();
	
	if (argc > 1)
		interval = atoi(argv[1]) ;
	
	if (argc == 3)
		delay = atoi(argv[2]) ;
		
	printf("\n Using Delay = %d  & Interval = %d",	delay, interval);
	while(1)
	{	store=0;
		monitor();
		sleep(delay);
		system("clear");
		
		store=1;
		monitor();
		
		sleep(interval);
		system("clear");
	}
/*
 * Memory management stuff .. To be done later	
	while (dom_first != dom_last)
	{
		 free(dom_first);
		 dom_first=dom_first->next;
	}
*/
	return(0);
}

