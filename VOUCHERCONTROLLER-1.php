<?php
public function add(){
    
    $user = $this->_ap_right_check();
    if(!$user){
        return;
    }
    
    $req_d    = $this->request->getData();  
    $check_items = [
        'activate_on_login',
        'never_expire'
    ];
                
    foreach($check_items as $i){
        if(isset($req_d[$i])){
            if($req_d[$i] == null){
                $req_d[$i] = 0;
            }else{
                $req_d[$i] = 1;
            }
        }else{
            $req_d[$i] = 0;
        }
    }
    
    //If it is expiring; set it in the correct format
    if(($req_d['never_expire'] == 0)&&(isset($req_d['expire']))){
        $newDate = date_create_from_format('Y-m-d', $req_d['expire']); //Submit format: 2026-02-02 (ISO) ISO 8601 format
        $req_d['expire'] = $newDate;
    }
    
    //---Set Realm related things--- 
    $realm_entity           = $this->Realms->entityBasedOnPost($req_d);
    if($realm_entity){
        $req_d['realm']   = $realm_entity->name;
        $req_d['realm_id']= $realm_entity->id;
        
        //Test to see if we need to auto-add a suffix
        $suffix          =  $realm_entity->suffix; 
        $suffix_vouchers = $realm_entity->suffix_vouchers;
       
    }else{
        $this->JsonErrors->errorMessage('realm or realm_id not found in DB or not supplied');
        return;
    }
    
    //---Set profile related things---
    $profile_entity = $this->Profiles->entityBasedOnPost($req_d);
    if($profile_entity){
        $req_d['profile']   = $profile_entity->name;
        $req_d['profile_id']= $profile_entity->id;
    }else{
        $this->JsonErrors->errorMessage('profile or profile_id not found in DB or not supplied');
        return;
    }

    //--Here we start with the work!
    $qty        = 1;//Default value
    $counter    = 0;
    $repl_fields= [
        'id', 'name', 'batch','created','extra_name','extra_value',
        'realm','realm_id','profile','profile_id','expire','time_valid'
    ];

    $created    = [];

    if(array_key_exists('quantity',$req_d)){
        $qty = $req_d['quantity'];
    }

    while($counter < $qty){
    
        if($req_d['single_field'] == 'false'){
            $p = '';
            if(array_key_exists('precede',$req_d)){
                if($req_d['precede'] !== ''){
                    $p = $req_d['precede'];
                }
            }
        
            $s = '';
            if(($suffix != '')&&($suffix_vouchers)){
                $s = $suffix;
            }      
            $un     = $this->VoucherGenerator->generateUsernameForVoucher($p,$s);
            $pwd    = $this->VoucherGenerator->generatePassword();
            $req_d['name']      = $un; 
            $req_d['password']  = $pwd;
            
        }else{
            // Use the SMS transaction ID as the actual voucher value for single-field vouchers
            $transaction_id = null;

            if(isset($req_d['transaction_id']) && $req_d['transaction_id'] !== ''){
                $transaction_id = $req_d['transaction_id'];
            }elseif(isset($req_d['extra_value']) && $req_d['extra_value'] !== ''){
                $transaction_id = $req_d['extra_value'];
            }elseif(isset($req_d['name']) && $req_d['name'] !== ''){
                $transaction_id = $req_d['name'];
            }

            if($transaction_id === null || trim($transaction_id) === ''){
                $this->JsonErrors->errorMessage(__('Transaction ID missing for single-field voucher'));
                return;
            }

            $pwd = $transaction_id;

            if(($suffix != '')&&($suffix_vouchers)){
                $pwd = $pwd.'@'.$suffix;
            }

            $req_d['name']      = $pwd; 
            $req_d['password']  = $pwd;

            // If you want to keep the SMS reference visible as metadata
            if(!isset($req_d['extra_name']) || $req_d['extra_name'] == ''){
                $req_d['extra_name'] = 'transaction_ref';
            }
            if(!isset($req_d['extra_value']) || $req_d['extra_value'] == ''){
                $req_d['extra_value'] = $transaction_id;
            }
        }
         
        $entity = $this->{$this->main_model}->newEntity($req_d);
        
        $this->{$this->main_model}->save($entity);
        if(!$entity->getErrors()){ //Hopefully taking care of duplicates is as simple as this :-)
            $counter = $counter + 1;
            $row     = [];
            foreach($repl_fields as $field){
                $row["$field"]= $entity->{"$field"};
            }
            array_push($created,$row);
            
            //OCT 2022 ADD A STEP TO REMOVE POTENTIAL OLD ORPHANED ACCOUNTIG RECORDS
            $n = $req_d['name'];
            $this->{'Radaccts'}->deleteAll(['Radaccts.username' => $n]);
            //END
            
        }            
    }
    
    $this->set([
        'success' => true,
        'data'    => $created
    ]);
    $this->viewBuilder()->setOption('serialize', true); 
} 